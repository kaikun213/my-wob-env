# proxy server to record and replay HTTP traffic.
import time
import threading
import logging
import urllib
import hashlib
import shelve
import base64
import os
import re
import json
from io import BytesIO

from mitmproxy import controller, options, master
from mitmproxy.io import FlowReader, FlowWriter
from mitmproxy.proxy import ProxyServer, ProxyConfig
from mitmproxy.utils import strutils
from mitmproxy.http import make_error_response
from mitmproxy import exceptions
from mitmproxy import ctx
from mitmproxy import io

from realwob.rewarders import WebRewarder
from realwob.db import KeyValueStore
from realwob.config import (IGNORE_SITE_PARAMS, IGNORE_URL_PARAMS,
                            WHITELIST_URL_PARAMS, IGNORE_DOMAINS)

logger = logging.Logger(name='realwob')
logger.setLevel(logging.WARNING)

class ProxyCache(object):
    def __init__(self, name):
        self.options = None

        self.stop = False
        self.final_flow = None

        # db stores serialized version.
        # flowmap stores states.
        self.db_scope = 'cache.' + name
        self.db = KeyValueStore(self.db_scope)
        self.flowmap = {}

        logger.warn('[DB] wob proxy db opened size = %d', len(self.db))

    def get(self, f):
        k = self._hash(f)
        if k in self.flowmap:
            return self.flowmap[k]
        # miss, fall back to slower db cache.
        if k not in self.db:
            self.flowmap[k] = []
            return self.flowmap[k]
        v = self.db[k]
        stream = BytesIO(v)
        reader = io.FlowReader(stream)
        flows = [flow for flow in reader.stream()]
        self.flowmap[k] = flows
        return flows

    def add(self, f):
        k = self._hash(f)
        flows = self.get(f)
        flows.append(f)
        self.flush(k) # TODO: flush lazily.

    def flush(self, key):
        ''' flush flows to db '''
        flows = self.flowmap[key]
        stream = BytesIO()
        writer = io.FlowWriter(stream)
        for flow in flows:
            writer.add(flow)
        self.db[key] = stream.getvalue()

    def close(self):
        logger.warn('closing caching')

    def count(self):
        return max(len(self.db), len(self.flowmap))

    def _hash(self, flow):
        ''' Calculates a loose hash of the flow request. '''
        r = flow.request

        _, netloc, path, _, query, _ = urllib.parse.urlparse(r.url)
        # these parameters will be ignored during matching.
        to_bytes = lambda params: [strutils.always_bytes(i) for i in params]
        ignore_site_params = IGNORE_SITE_PARAMS.get(netloc, [])
        ignore_url_params= IGNORE_URL_PARAMS.get(netloc + path, [])
        whitelist_url_params = WHITELIST_URL_PARAMS.get(netloc + path, None)

        queriesArray = urllib.parse.parse_qsl(query, keep_blank_values=True)

        key = [str(r.port), str(r.scheme), str(r.method), str(path)]

        headers = dict(r.data.headers)
        form_contents = r.urlencoded_form or r.multipart_form
        form_items = []

        if re.match(r'application/.*json', headers.get('content-type', '')):
            form_unsorted = json.loads(r.data.content.decode('utf-8'))
            if isinstance(form_unsorted, list): # make sure form is a dict.
                form_unsorted = {'data': form_unsorted }
            form_items = [(k, json.dumps(form_unsorted[k], sort_keys=True))
                          for k in sorted(form_unsorted.keys())]
        elif form_contents:
            form_items = form_contents.items(multi=True)

        if form_items:
            for p in form_items:
                param = strutils.always_bytes(p[0])
                if param in to_bytes(ignore_site_params) or param in to_bytes(ignore_url_params):
                    logger.warn('[proxy hash] ignoring parameter %s', str(p[0]))
                    continue

                if whitelist_url_params and param not in to_bytes(whitelist_url_params):
                    logger.warn('[proxy hash] ignoring parameter %s', str(p[0]))
                    continue

                key.append(p)
        else:
            key.append(str(r.raw_content))

        if not self.options.server_replay_ignore_host:
            key.append(r.host)

        filtered = []

        for p in queriesArray:
            param = p[0]
            if param in ignore_site_params or param in ignore_url_params:
                logger.warn('[proxy hash] ignoring parameter %s', str(p[0]))
                continue

            if whitelist_url_params and param not in whitelist_url_params:
                logger.warn('[proxy hash] ignoring parameter %s', str(p[0]))
                continue

            filtered.append(p)
        for p in filtered:
            key.append(p[0])
            key.append(p[1])

        if self.options.server_replay_use_headers:
            headers = []
            for i in self.options.server_replay_use_headers:
                v = r.headers.get(i)
                headers.append((i, v))
            key.append(headers)
        binary = hashlib.sha256(
            repr(key).encode("utf8", "surrogateescape")
        ).digest()

        if r.method == 'POST':
            logger.warn('\033[91m Args %s \033[0m',
                repr(key).encode("utf8", "surrogateescape")
            )
        return str(base64.b64encode(binary), 'utf8')

    def configure(self, options, updated):
        self.options = options
        if "server_replay" in updated:
            self.clear()
            if options.server_replay:
                try:
                    flows = io.read_flows_from_paths(options.server_replay)
                except exceptions.FlowReadException as e:
                    raise exceptions.OptionsError(str(e))
                self.load(flows)

    def request(self, f, kill_miss=False):
        ''' return whether the request is killed '''
        _, netloc, _, _, _, _ = urllib.parse.urlparse(f.request.url)

        # some websites use certificate pinning to prevent Man-In-Middle attach.
        # this means our cache fails so we should avoid making requests to them.
        if netloc in IGNORE_DOMAINS:
            f.response = make_error_response(404, 'ignore requested domain')
            return True

        # reject https connect requests since we don't support them.
        if f.request.data.method == 'CONNECT':
            f.reply.kill()
            return True

        rflows = self.get(f)

        if rflows:
            rflow = rflows[-1]
            response = rflow.response.copy()
            response.is_replay = True
            if self.options.refresh_server_playback:
                response.refresh()
            f.response = response
            if not self.flowmap and not self.options.keepserving:
                self.final_flow = f
                self.stop = True
        elif kill_miss:
            logger.warn(
                "server_playback: killed non-replay request {}".format(
                    f.request
                )
            )
            f.response = make_error_response(404, 'ignore requested domain')
            return True
        return False


class ProxyController(master.Master):
    def __init__(self, mode, cache_path, rewarders=[]):
        opts = options.Options(cadir="~/.mitmproxy/")
        opts.listen_port = 8888
        config = ProxyConfig(opts)
        server = ProxyServer(config)
        super(ProxyController, self).__init__(opts, server)

        self.mode = mode

        self.cache = ProxyCache(cache_path)
        self.cache.configure(opts, {})

        self.WOB_LOCK = threading.Lock()
        self.WOB_REWARD_GLOBAL = 0
        self.WOB_DONE_GLOBAL = False
        self.rewarders = rewarders

    def update_reward(self, reward, done_flag):
        logger.info('[ProxyController] Update Reward %s %s', str(reward), str(done_flag))
        self.WOB_LOCK.acquire()
        self.WOB_REWARD_GLOBAL += reward
        if not self.WOB_DONE_GLOBAL:
            self.WOB_DONE_GLOBAL = done_flag
        self.WOB_LOCK.release()

    def run(self):
        try:
            master.Master.run(self)
        except KeyboardInterrupt:
            self.shutdown()

    def close(self):
        self.cache.close()

    def reset(self):
        logger.warn('resetting server setting done false')
        self.WOB_LOCK.acquire()
        self.WOB_REWARD_GLOBAL = 0.
        self.WOB_DONE_GLOBAL = False
        self.WOB_LOCK.release()
        logger.warn('resetting server setting done done')

    def run_tick(self):
        try:
            while not self.should_exit.is_set():
                # Don't choose a very small timeout in Python 2:
                # https://github.com/mitmproxy/mitmproxy/issues/443
                # TODO: Lower the timeout value if we move to Python 3.
                self.tick(0.1)
        finally:
            self.shutdown()

    def start(self):
        super(ProxyController, self).start()
        thread = threading.Thread(target=self.run_tick)
        thread.start()

    def reward(self, f):
        for rewarder in self.rewarders:
            (reward, done_flag) = rewarder.observe_flow(f)
            self.update_reward(reward, done_flag)

    @controller.handler
    def request(self, f):
        logger.info('[downstream request] %s', str(f.request))
        if self.mode == 'ENV':
            killed = self.cache.request(f, kill_miss=True)
        elif self.mode == 'DATA':
            killed = self.cache.request(f, kill_miss=False)

        if not killed: self.reward(f)

    @controller.handler
    def response(self, f):
        logger.info('[upstream response] %s', str(f))
        if self.mode == 'DATA':
            self.cache.add(f)

    @controller.handler
    def error(self, f):
        logger.error(f)

    @controller.handler
    def log(self, l):
        logger.info(l.msg)



