#!/usr/bin/env python
from __future__ import print_function
import threading
import argparse
import manhole
import random
import time
import six
import sys
import os
import json
if six.PY2:
    import Queue as queue
    import urlparse
else:
    import queue
    import urllib.parse as urlparse
import re

from selenium import webdriver

import universe
from universe.rewarder import remote
from universe import twisty, wrappers

import tornado
import socket

from backend.server import MOCK_PORT, MockServer, ioloop
from config import global_registry, WEBDRIVER_DEVICES

from realwob import ProxyController

# -----------------------------------------------------------------------------
# Logging and setup
# -----------------------------------------------------------------------------
import logging
logger = logging.getLogger()
logger.setLevel(logging.WARN)

twisty.start_once()
# selenium can be very verbose, calm it down
# (see http://stackoverflow.com/questions/23407142/how-do-i-reduce-the-verbosity-of-chromedriver-logs-when-running-it-under-seleniu)
from selenium.webdriver.remote.remote_connection import LOGGER
#LOGGER.setLevel(logging.WARNING)

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def safe_execute(browser, cmd, default=None):
    """ safely execute something in browser and log errors as needed """
    if browser is None:
        print('Browser is not ready yet.')
        return default
    try:
        ret = browser.execute_script(cmd)
        return ret
    except Exception as e:
        logger.info(e)
        return default

# -----------------------------------------------------------------------------
# Env controller thread.
# -----------------------------------------------------------------------------
class EnvController(threading.Thread):
    daemon = True

    def __init__(self, env_status, agent_conn, error_buffer, control_buffer, mode='DATA'):
        super(EnvController, self).__init__(name='EnvController')
        self.cv = threading.Condition()
        self.browser = None
        self.server = None
        self.init_browser = False
        self.init_server = False
        self.init_reset = False
        self.mode = mode
        self.setting = {}

        self.env_status = env_status
        self.agent_conn = agent_conn
        self.error_buffer = error_buffer
        self.control_buffer = control_buffer

        # variables for iterating over miniwob envs, when env_id is wob.MiniWob
        self.miniwob_envs = [k for k,v in global_registry.items() if type(v) == str and 'miniwob' in v]
        random.shuffle(self.miniwob_envs)
        self.miniwob_pointer = 0 # point to the next miniwob env to load
        print('[EnvController] found %d miniwob envs' % (len(self.miniwob_envs)), )

        self.load_env()

    def load_env(self):
        env_id = self.env_status.env_id

        if env_id == 'wob.MiniWorldOfBits-v0':
            # special case, cycle through envs
            assert len(self.miniwob_envs) > 0, 'There were 0 miniwob envs detected?! See the EnvController code'
            wob_env_id = self.miniwob_envs[self.miniwob_pointer]
            self.miniwob_pointer += 1
            if self.miniwob_pointer >= len(self.miniwob_envs):
                self.miniwob_pointer = 0 # wrap around
            registry_item = global_registry[wob_env_id]
        else:
            registry_item = global_registry[env_id]


        # parse url.
        # setting is a dict with the following fields.
        #   - reload: if set to True, will reload webpage whenever task resets.
        if type(registry_item) == str:
            # miniwob: javascript only mini enviroments.
            self.url = registry_item
            parsed_url = urlparse.urlparse(self.url)
            self.setting = {
                'scheme': 'miniwob',
                'path': parsed_url.path,
                'www': 'static',
                'server': None,
                'reload': False
            }
        elif type(registry_item) == dict and registry_item['type'] == 'mockwob':
            # mockwob: mini enviroments + a mock backend in tornado.
            self.parsed_url = registry_item
            self.url = 'http://localhost:' + str(MOCK_PORT)
            self.setting = {
                'scheme': 'mockwob',
                'path': '/',
                'www': registry_item['www'],
                'server': registry_item['server'],
                'reload': registry_item.get('reload', False)
            }
        elif type(registry_item) == dict and registry_item['type'] == 'realwob':
            # realwob: real environments with truly real websites.
            self.parsed_url = registry_item
            self.url = registry_item['www']
            self.setting = {
                'scheme': 'realwob',
                'path': '/',
                'www': registry_item['www'],
                'db': registry_item['db'],
                'rewarder': registry_item.get('rewarder'),
                'device': registry_item.get('device', ''),
                'reload': registry_item.get('reload', False)
            }
        else:
            raise ValueError('unknown registry entry type ' + str(registry_item))

    def run(self):
        try:
            self.do_run()
        except Exception as e:
            self.error_buffer.record(e)

    def do_run(self):
        try:
            # initialize the mock server if necessary.
            self.launch_server()

            # initialize the browser
            self.launch_browser()

            # reset env.
            self.reset()
            self.init_reset = True

        except Exception as e:
            self.error_buffer.record(e)

        # and loop
        try:
            while True:
                self.process_control_messages()
                self.agent_conn.check_status()

                with self.cv:
                    self.cv.wait(timeout=1)

                if self.env_status.env_state == 'resetting':
                    self.reset()
        except KeyboardInterrupt:
            logger.warn('keyboard interrupt in thread')
            try:
                if self.server:
                    self.server.close()
                if self.rewarder:
                    self.rewarder.close()
            except Exception as e:
                self.error_buffer.record(e)

    def launch_server(self):
        if self.setting['scheme'] == 'miniwob':
            self.server = None
            self.rewarder = None

        elif self.setting['scheme'] == 'mockwob':
            # TODO: decouple server and rewarder.
            self.server = self.setting['server'](self.setting['www'])
            self.rewarder = None
            self.server.start()
            logging.info('mock server started: ' + self.setting['www'])

        elif self.setting['scheme'] == 'realwob':
            logger.info('launching cache proxy server...')
            if self.setting.get('rewarder'):
                self.rewarder = self.setting['rewarder'](self.mode)
                logger.warn('initializing %s', self.setting['rewarder'](self.mode))
                rewarders = [self.rewarder]
            else:
                self.rewarder = None
                rewarders = []
            self.server = ProxyController(mode=self.mode,
                                          cache_path=self.setting['db'],
                                          rewarders=rewarders)
            self.server.start()
            logger.info('cache proxy server started - mode = %s', self.mode)

        self.init_server = True

    def launch_browser(self):
        if self.env_status.env_state != 'resetting':
            self.env_status.set_env_info('resetting')

        print('Launching new Chrome process...')
        chrome_options = webdriver.ChromeOptions()

        # needed to start chrome instance
        chrome_options.add_argument('--no-sandbox')

        # disable infobar to remove "Chrome is controlled by automated software"
        chrome_options.add_argument("--disable-infobars");

        if self.setting['scheme'] == 'realwob':
            # disable browser cache.
            chrome_options.add_argument('--disable-application-cache')
            #chrome_options.add_argument('--proxy-server=0.0.0.0:8888')
            chrome_options.add_argument('--ignore-certificate-errors')
            if self.setting.get('device'):
                print('setting device', self.setting['device'])
                chrome_options.add_experimental_option('mobileEmulation',
                                                       WEBDRIVER_DEVICES[self.setting['device']])


        # start browser.
        self.browser = webdriver.Chrome(chrome_options=chrome_options)
        self.browser.command_executor._conn.timeout = 5 # This is needed so that selenium doesn't hang forever if someone exited the chrome tab.
        self.browser.set_page_load_timeout(30)          # seconds timeout for pages.

        # tell rewarder about browser.
        if self.rewarder:
            self.rewarder.init_browser(self.browser)

        self.init_browser = True

    def process_control_messages(self):
        while True:
            try:
                type, payload = self.control_buffer.get(block=False)
            except queue.Empty:
                break
            else:
                if type == 'rpc':
                    context, message = payload
                    self.process_rpc(context, message)
                elif type == 'client_disconnect':
                    pass
                else:
                    assert False, 'Unrecogized type: {}'.format(type)

    def process_rpc(self, context, message):
        if message['method'] == 'v0.env.reset':
            env_id = message['body']['env_id']
            episode_id = message['headers']['episode_id']
            if env_id not in global_registry and env_id != 'wob.MiniWorldOfBits-v0':
                self.agent_conn.send_reply_error(
                    message="No server-side registration for {}. (HINT: This is the runtime for World of Bits. Perhaps you tyop'd the ID or it's meant for a different runtime.)".format(env_id),
                    parent_message_id=message['headers']['message_id'],
                    parent_context=context,
                )
                return

            # TODO: validate env_id
            env_info = self.env_status.set_env_info('resetting', env_id=env_id, bump_past=episode_id)

            if env_id != self.env_status.env_id or env_id == 'wob.MiniWorldOfBits-v0':
                old_setting = dict(self.setting)
                self.load_env()
                # restart browser if device and scheme changes.
                if (self.setting.get('scheme') != old_setting.get('scheme') or
                    self.setting.get('device') != old_setting.get('device')):
                    if self.browser:
                        self.browser.quit()
                    if self.server:
                        self.server.shutdown()
                    self.init_browser = False
                    self.init_server = False
                    self.launch_browser()
                    self.launch_server()

            self.reset()
            self.agent_conn.send_reply_env_reset(
                parent_message_id=message['headers']['message_id'],
                parent_context=context,
                episode_id=self.env_status.episode_id,
            )
        else:
            self.agent_conn.send_reply_error(
                'Unsupported RPC method: {}'.format(message['method']),
                parent_message_id=message['headers']['message_id'],
                parent_context=context
            )

    @property
    def instruction(self):
        if self.setting['scheme'] == 'mockwob' and self.server:
            return self.server.instruction
        elif self.setting['scheme'] == 'realwob' and self.rewarder:
            return self.rewarder.instruction
        else:
            return ''

    @instruction.setter
    def instruction(self, new_instruction):
        if self.setting['scheme'] == 'mockwob' and self.server:
            self.server.instruction = new_instruction
        elif self.setting['scheme'] == 'realwob' and self.rewarder:
            self.rewarder.instruction = new_instruction
        self.agent_conn.send_env_text({'instruction': new_instruction}, episode_id=self.env_status.episode_id)
        logger.warn('[instruction] Sent env text %s', new_instruction)

    def trigger_reset(self):
        logger.info('Triggering a reset on EnvController')
        with self.cv:
            self.env_status.set_env_info('resetting')
            self.cv.notify()

    def reset(self):
        env_info = self.env_status.env_info()  # Be sure to only call this once, as it can change from under us.
        assert env_info['env_state'] == 'resetting', 'Env state should be resetting, but is instead: {}'.format(env_info['env_state'])
        self.agent_conn.send_env_describe_from_env_info(env_info)

        # change the url/setting/etc potentially based on env_status
        self.load_env()

        # restart backend server if exists.
        if self.server:
            logger.info('Restarting HTTP server')
            self.server.reset()

        # clear all cookies.
        #while True:
        #    try:
        #        self.browser.delete_all_cookies()
        #        break
        #    except:
        #        logger.warn('Trying to delete cookie')
        #        time.sleep(1.)


        # point browser to target url.
        # if this step happens when the browser is busy with another
        # redirection. an exception will occur at
        # self.browswer.current_url. So we keep trying with a loop.
        while True:
            try:
                if self.browser.current_url != self.url or self.setting.get('reload'):
                    logging.info('changing url to ' + self.url)
                    print('window.location.replace("{}")'.format(self.url))
                    safe_execute(self.browser, 'window.location.replace("{}")'.format(self.url))
                # window replace is successful.
                break
            except socket.timeout:
                logger.warn('Browser reset timeout, stop.')
                break
            except Exception as e:
                logger.warn('Browser reset failed: %s', str(e))
                time.sleep(1.)
                #self.error_buffer.record(e)

        # wait for the browser to load.
        while True:
            dom_state = safe_execute(self.browser, 'return document.readyState;')
            logger.warn('Waiting for document to load: %s', dom_state)
            if dom_state == 'complete':
                break
            time.sleep(1.)

        # reset rewarder.
        while self.rewarder:
            try:
                self.rewarder.reset()
                break
            except Exception as e:
                logger.warn('Rewarder reset failed. Trying again. %s', str(e))
                time.sleep(1.)

        # set environment state.
        env_info = self.env_status.set_env_info('running')
        self.agent_conn.send_env_describe_from_env_info(env_info)

        with self.cv:
            self.cv.notifyAll()

    def close(self):
        # close env server.
        if self.server:
            self.server.close()
            self.server = None
        # close rewarder
        if self.rewarder:
            self.rewarder.close()
            self.rewarder = None
        # close browser.
        if self.browser:
            self.browser.close()
            self.browser = None



# TODO: this is a hack. eventually we want everything to follow RPC.
class EnvControllerServer(object):
    ''' provide control API wrapper of the env '''
    daemon = True
    API_PORT = 8889

    class SetInstructionHandler(tornado.web.RequestHandler):
        def initialize(self, server):
            self.server = server

        def post(self):
            body = self.request.body.decode('utf-8')
            args = json.loads(body)
            logger.warn('[set instruction] %s', str(args))
            instruction = args['instruction']
            self.server.env_controller.instruction = instruction

    class ResetHandler(tornado.web.RequestHandler):
        ''' trigger env_controller reset async '''
        def initialize(self, server):
            self.server = server

        def get(self):
            self.server.rewarder.reset_env()

    def __init__(self, env_controller, rewarder):
        self.env_controller = env_controller
        self.rewarder = rewarder

        self.settings = {
            "autoreload": True,
            "debug": True,
        }

        self.handlers = [
            (r"/set_instruction", EnvControllerServer.SetInstructionHandler, {'server': self}),
            (r"/reset", EnvControllerServer.ResetHandler, {'server': self})
        ]

    def start(self):
        self.app = tornado.web.Application(self.handlers, **self.settings)
        self.http_server = self.app.listen(self.API_PORT, address="0.0.0.0")

    def stop(self):
        self.http_server.stop()


# -----------------------------------------------------------------------------
# Rewarder thread.
# -----------------------------------------------------------------------------
class Rewarder(threading.Thread):
    """
    The job the Rewarder thread is to periodically (e.g. at 60Hz) communicate
    {reward, done, info} over the agent_conn.
    """
    daemon = True

    def __init__(self, env_status, agent_conn, env_controller, error_buffer, fps=60):
        logger.info("Rewarder initialized")

        super(Rewarder, self).__init__(name='Rewarder',)
        self.agent_conn = agent_conn
        self.env_controller = env_controller
        self.env_status = env_status
        self.error_buffer = error_buffer

        self.fps = fps # at what fps to run

    def run(self):
        try:
            self.do_run()
        except Exception as e:
            self.error_buffer.record(e)

    def _read_client_done(self, browser):
        done = safe_execute(browser, """ try { return WOB_DONE_GLOBAL; } catch(err) { return false; } """, default=False)
        return done

    def _read_server_done(self, server):
        if server:
            return server.WOB_DONE_GLOBAL
        else:
            return False

    def _read_client_reward(self, browser):
        ''' read reward off the client (javascript) and set the original value to zero.
        '''
        # TODO: this is not atomic right?
        reward = safe_execute(browser, """ return WOB_REWARD_GLOBAL; """, default=0)
        safe_execute(self.env_controller.browser, """ WOB_REWARD_GLOBAL = 0;""")
        done = self._read_client_done(browser)
        return (reward, done)

    def _read_server_reward(self, server):
        ''' read reward off the server and set the original value to zero.
        '''
        if server is None: # serverless env.
            return (0, False)

        server.WOB_LOCK.acquire()
        reward = server.WOB_REWARD_GLOBAL
        done = self._read_server_done(server)
        server.WOB_REWARD_GLOBAL = 0
        server.WOB_LOCK.release()
        return (reward, done)

    def reset(self):
        browser = self.env_controller.browser
        server = self.env_controller.server

        while self._read_client_done(browser):
            logger.warn('Waiting for client to reset')
            time.sleep(0.25)

        while self._read_server_done(server):
            logger.warn('Waiting for server to reset')
            time.sleep(0.25)

        if self.env_controller.setting['scheme'] == 'miniwob':
            # we rely on the client to tell us if the env being reset is ready.
            #   when the env is being reset, WOB_DONE_GLOBAL is set to true.
            #   when a new episode is ready, WOB_DONE_GLOBAL is set to false.
            # miniwob is being reset.
            self.env_controller.instruction = safe_execute(browser, "return document.querySelector('#query').textContent", '')
        elif self.env_controller.setting['scheme'] == 'realwob' and self.env_controller.rewarder:
            self.env_controller.instruction = self.env_controller.rewarder.instruction
        logger.warn('instruction generated %s', self.env_controller.instruction)

    def reset_env(self):
        self.env_controller.trigger_reset()
        while self.env_controller.env_status.env_state == 'resetting':
            logger.info('Rewarder waiting for env to be reset')
            time.sleep(0.1)

        self.reset()

    def do_run(self):
        # wait for browser to come online
        while not self.env_controller.init_browser:
            logger.info('Rewarder thread is waiting for the browser instance...')
            time.sleep(0.25)

        # wait for server to come online
        while not self.env_controller.init_server:
            logger.info('Rewarder thread is waiting for the server instance...')
            time.sleep(0.25)

        # wait for first reset to be done.
        while not self.env_controller.init_reset:
            logger.info('Rewarder thread is waiting for first reset to finish...')
            time.sleep(0.25)

        self.reset()

        # start the main loop
        t0 = time.time()
        n = 0

        while True:
            # timing/sleeping computations to pursue fixed self.fps to best of our ability
            n += 1
            t = t0 + n * 1.0 / self.fps
            dt = t - time.time()
            if dt > 0:
                time.sleep(dt)
            else:
                logger.info('Rewarder falling behind %f', dt)

            # interact with the browser/server instance to read off current rewards and done flag
            (reward_client, done_client) = self._read_client_reward(self.env_controller.browser)
            (reward_server, done_server) = self._read_server_reward(self.env_controller.server)
            reward = reward_client + reward_server
            done = done_client or done_server # if one of them quit, the env ends.

            if done:
                if self.env_controller.setting['scheme'] == 'miniwob':
                    self.agent_conn.send_env_text({'info': 'done! reward=%0.2f' % reward}, episode_id=self.env_status.episode_id)
                elif self.env_controller.setting['scheme'] == 'realwob':
                    if self.env_controller.mode == 'ENV':
                        self.agent_conn.send_env_text({'info': 'done! reward=%0.2f' % reward}, episode_id=self.env_status.episode_id)
                    elif self.env_controller.mode == 'DATA':
                        self.agent_conn.send_env_text({'info': 'Done, good job!'}, episode_id=self.env_status.episode_id)

            if reward != 0:
                logger.info('Sending reward to agent: reward=%0.2f done=%s', reward, done)
                self.agent_conn.send_env_reward(reward, done, {}, episode_id=self.env_status.episode_id)

            if done:
                self.reset_env()
                n = 0
                t0 = time.time()

class IOThread(threading.Thread):
    daemon = True

    def __init__(self, env_controller, error_buffer):
        super(IOThread, self).__init__()
        self.env_controller = env_controller
        self.error_buffer = error_buffer

    def run(self):
        try:
            ioloop.IOLoop.current().start()
        except KeyboardInterrupt:
            logger.warn('keyboard interrupt in thread')
            try:
                self.env_controller.close()
            except Exception as e:
                self.error_buffer.record(e)
            ioloop.IOLoop.current().stop()

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():

    # command line option handling
    parser = argparse.ArgumentParser(description=None)
    parser.add_argument('-e', '--env_id', default='wob.mini.ClickShape-v0', help='env id')
    parser.add_argument('-v', '--verbose', action='count', dest='verbosity', default=0, help='Set verbosity.')
    parser.add_argument('-m', '--mode', default='DATA', help='mode (DATA | ENV | DEMO)')
    parser.add_argument('-f', '--fps', default=15, type=int, help='Number of frames per second')
    parser.add_argument('-i', '--idle-timeout', type=float, help='How long to keep the environment around when it has no active connections')
    args = parser.parse_args()
    print(args)

    # logging and setup
    if args.verbosity == 0:
        logger.setLevel(logging.INFO)
    elif args.verbosity >= 1:
        logger.setLevel(logging.DEBUG)
        logger.info("Starting world of bits run.py with: %s", sys.argv)

    error_buffer = universe.utils.ErrorBuffer()

    # Jot down the env_id so the uploader can find it later
    env_id_file_dir = os.path.join(os.sep, 'tmp', 'demo')
    env_id_file_path = os.path.join(env_id_file_dir, 'env_id.txt')
    if not os.path.exists(env_id_file_dir):
        logger.info("[world-of-bits] Creating directory %s", env_id_file_dir)
        os.makedirs(env_id_file_dir)

    try:
        with open(env_id_file_path,'w') as env_id_file:
            logger.info("[world-of-bits] Writing env id to file %s", env_id_file_path)
            env_id_file.write(args.env_id)
            env_id_file.write('\n')
    except PermissionError:
        logger.info("[world-of-bits] could not write env id to " + env_id_file_path + " due to a permission error. skipping.")
        pass

    # create connection to the agent
    env_status = universe.rewarder.EnvStatus()
    env_status.set_env_info(env_id=args.env_id, fps=args.fps)
    cv = threading.Condition()
    control_buffer = remote.ControlBuffer(cv)
    agent_conn = remote.AgentConn(env_status, cv, control_buffer, error_buffer=error_buffer, idle_timeout=args.idle_timeout)
    agent_conn.listen()
    logger.info("Started AgentConn.")

    # start up the environment controller
    env_controller = EnvController(env_status, agent_conn, error_buffer, control_buffer, args.mode)
    env_controller.start()

    # start up the rewarder
    rewarder = Rewarder(env_status, agent_conn, env_controller, error_buffer, fps=args.fps)
    rewarder.start()

    # start up the environment controller API server.
    env_controller_api = EnvControllerServer(env_controller, rewarder)
    env_controller_api.start()

    # run the iothread
    iothread = IOThread(env_controller, error_buffer)
    iothread.start()

    # Debugging tool
    manhole.install(locals={'rewarder': rewarder, 'env_controller_api': env_controller_api, 'env_controller': env_controller, 'agent_conn': agent_conn})

    while True:
        try:
            error_buffer.blocking_check(timeout=60)
        except remote.Exit as e:
            logger.info('%s', e)
            return 0

if __name__ == '__main__':
  sys.exit(main())
