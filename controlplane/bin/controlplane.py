#!/usr/bin/env python
import argparse
import logging
import manhole
import os
import pipes
import signal
import six
import subprocess
import sys
import threading
import time
import traceback

if six.PY2:
    import Queue as queue
else:
    import queue

from PIL import Image

import gym

import universe
from universe import pyprofile, rewarder, twisty, wrappers
from universe.envs import vnc_env
from universe.rewarder import remote

import gym_controlplane
from gym_controlplane import error, utils

gym_controlplane.logger_setup()
logger = logging.getLogger()

# Needed only in development, where we can run os._exit. In this case,
# we want to kill any outstanding vexpects.
manual_subprocess_cleanup = {}

class Exit(Exception):
    pass

class EnvController(threading.Thread):
    def __init__(self, env, vnc_address, env_status, agent_conn, error_buffer, control_buffer, no_vexpect, integrator_mode):
        super(EnvController, self).__init__(name='EnvController')

        self._sweep_id = 0
        self._last_reset_sweep_id = 0

        self.env = env
        self.vnc_address = vnc_address
        self.env_status = env_status
        self.agent_conn = agent_conn
        self.control_buffer = control_buffer

        self.daemon = True
        self.error_buffer = error_buffer

        self.no_vexpect = no_vexpect
        self.integrator_mode = integrator_mode

        # self.cv = threading.Condition()
        self.cv = control_buffer.cv

        self.healthcheck_fail_countdown = 0
        self._healthcheck_fail_max = 5

        self.load_env(env_status.env_id)
        # Run this in main thread
        self.reset()

    def load_env(self, env_id):
        if env_id is not None:
            spec = gym_controlplane.spec(env_id)
        else:
            spec = None
        self.controlplane_spec = spec
        self.env_launcher = gym_controlplane.env_launcher(
            spec,
            integrator_mode=self.integrator_mode,
        )

    def trigger_reset(self):
        logger.info('[%s] Triggering a reset on EnvController', utils.thread_name())
        with self.cv:
            self.env_status.set_env_info('resetting')
            self.cv.notify()

    def run(self):
        try:
            self.do_run()
        except Exception as e:
            self.error_buffer.record(e)

    def do_run(self):
        while True:
            self.process_control_messages()
            self.agent_conn.check_status()

            if self.env_launcher is not None:
                healthy = self.env_launcher.healthcheck()
            else:
                healthy = True

            if healthy:
                self.healthcheck_fail_countdown = 0
            else:
                self.healthcheck_fail_countdown += 1
                logger.info('[%s] Environment failed healthcheck! Count: %s',
                    utils.thread_name(),
                    self.healthcheck_fail_countdown)

            if self.healthcheck_fail_countdown > self._healthcheck_fail_max:
                logger.info('[%s] RESET CAUSE: environment healthcheck failed too many times!', utils.thread_name())
                self.agent_conn.send_env_reward(0, True, {'reason': 'controlplane.browser_crashed'}, episode_id=self.env_status.episode_id)
                # This will reset the environment
                self.reset()

            # Notified when the environment starts resetting, or when
            # new control messages are available
            with self.cv:
                self.cv.wait(timeout=1)

            if self.env_status.env_state == 'resetting':
                logger.info('[%s] controlplane.py is resetting the environment', utils.thread_name())
                self.reset()

    def process_control_messages(self):
        self._sweep_id += 1
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
                    conn, stats = payload
                    self.process_disconnect(conn, stats)
                else:
                    assert False, 'Unrecogized type: {}'.format(type)

    def process_disconnect(self, conn, stats):
        pass

    def process_rpc(self, context, message):
        if message['method'] == 'v0.env.reset':
            env_info = self.env_status.env_info()
            env_id = message['body']['env_id']
            fps = message['body']['fps']
            if fps < 0 or fps > 60:
                logger.warn('[%s] Ignoring request for bad fps=%s', fps)
                fps = None

            changing_id = env_id != env_info['env_id']
            changing_fps = fps != env_info['fps']

            if changing_id:
                # Validate the env ID before altering any state
                try:
                    gym_controlplane.spec(env_id)
                except error.UserError as e:
                    self.agent_conn.send_reply_error(
                        e.user_message,
                        parent_message_id=message['headers']['message_id'],
                        parent_context=context
                    )
                    pyprofile.incr('control.env_id_change.user_error')
                    return

            episode_id = message['headers']['episode_id']
            if not changing_id and not changing_fps and \
               rewarder.compare_ids(episode_id, env_info['episode_id']) < 0 and \
               self._sweep_id == self._last_reset_sweep_id:
                # The user hasn't requested any changes, and our
                # current episode_id is ahead of the requested one,
                # and we're in the middle of resetting -- they may as
                # well just piggyback on our current reset.
                logger.info('[%s] SKIPPING RESET: user requested reset, but already reset in this sweep and no changes requested: request: env_id=%s fps=%s episode_id=%s current: episode_id=%s. Short circuiting by just using the current reset.', utils.thread_name(), env_id, fps, episode_id, env_info['episode_id'])
                short_circuit = True
            else:
                logger.debug('Change requested: changing_id=%s changing_fps=%s compare_ids=%s state=%s sweep_id=%s last_reset_sweep_id=%s',
                             changing_id, changing_fps,
                             rewarder.compare_ids(episode_id, env_info['episode_id']),
                             env_info['env_state'], self._sweep_id, self._last_reset_sweep_id)
                # Make sure we're resetting before changing the env_id
                env_info = self.env_status.set_env_info('resetting', env_id=env_id, bump_past=episode_id)
                short_circuit = False
            if not short_circuit:
                if changing_id:
                    self.load_env(env_id)

                    pyprofile.incr('control.env_id_change')
                    pyprofile.incr('control.env_id_change.{}'.format(env_id))
                    logger.info('[%s] RESET CAUSE: changing out environments due to v0.env.reset (with episode_id=%s): %s -> %s (new episode_id=%s fps=%s)', utils.thread_name(), episode_id, env_info['env_id'], env_id, env_info['episode_id'], fps)
                else:

                    logger.info('[%s] RESET CAUSE: Resetting environment due to v0.env.reset (with episode_id=%s), keeping same env_id=%s: new episode_id=%s fps=%s',
                                utils.thread_name(), episode_id, env_id, env_info['episode_id'], fps)

                self.reset()
            # We let the agent know the new episode_id to care
            # about. (In theory, we could do this before the reset
            # completes, but the aggregation case would then behave
            # differently.)
            self.agent_conn.send_reply_env_reset(
                episode_id=env_info['episode_id'],
                parent_message_id=message['headers']['message_id'],
                parent_context=context,
            )
        else:
            logger.warn('Ignoring unsupported message: %s', message)

    def reset(self):
        # We want to aggregate multiple reset calls into a single
        # reset. Thus, we record the sweep ID when we last
        # reset. (Note that this includes resets triggered
        # automatically rather than by the user.)
        self._last_reset_sweep_id = self._sweep_id

        # Mark ourselves as resetting if no one else did.
        with self.env_status.cv:
            if self.env_status.env_state != 'resetting':
                self.env_status.set_env_info('resetting')

        # This can change from under us, so only want to call env_info once to extract all state
        env_info = self.env_status.env_info()
        logger.info('[%s] Env state: env_id=%s episode_id=%s', utils.thread_name(), env_info['env_id'], env_info['episode_id'])
        assert env_info['env_state'] == 'resetting', 'Env state should be resetting, but is instead: {}'.format(env_state)
        # In the future, may choose to block on the user replying,
        # which would let us know they won't mess with our
        # initialization sequence. In practice this hasn't seemed to
        # be an issue.
        self.agent_conn.send_env_describe_from_env_info(env_info)

        # If in demo mode, let the demonstration code know what env is
        # active
        write_env_id(self.env_status.env_id)

        for i in range(5):
            if self.env_launcher is not None:
                self.env_launcher.reset()
            status = self._setup()
            # If need to repeat, will have logged the reason in _setup.
            if status is None:
                break

        self.env_status.env_state = 'running'

        env_info = self.env_status.env_info()
        self.agent_conn.send_env_describe_from_env_info(env_info)

        with self.cv:
            self.cv.notifyAll()

    def _setup(self):
        if not self.controlplane_spec:
            return
        elif not os.path.exists(self.controlplane_spec.vexpect_path):
            # TODO: DRY this up
            logger.info('[%s] Skipping vexpect initialization since no macro present', utils.thread_name())
            return
        elif self.no_vexpect:
            logger.info('[%s] Skipping vexpect initialization as configured', utils.thread_name())
            return
        cmd = [os.path.abspath(os.path.join(os.path.dirname(__file__), '../bin/play_vexpect')), '-e', self.controlplane_spec.id, '-r', self.vnc_address, '-d']
        logger.info('[%s] Running command: %s', utils.thread_name(), utils.pretty_command(cmd))
        proc = subprocess.Popen(cmd)
        manual_subprocess_cleanup[proc.pid] = proc
        proc.communicate()
        del manual_subprocess_cleanup[proc.pid]

        if proc.returncode == 0:
            return
        elif proc.returncode == 10:
            logger.info('[%s] RESET CAUSE: VExpect failed with returncode 10, which means it timed out internally. Going to trigger a reset.', utils.thread_name())
            self.trigger_reset()
            return 'fail'
        else:
            raise error.Error('Bad returncode {} from {}'.format(proc.returncode, utils.pretty_command(cmd)))

    def close(self):
        if self.env_launcher is not None:
            self.env_launcher.close()
        self.env_launcher = None

class Rewarder(threading.Thread):
    def __init__(self, env, vnc_address, agent_conn, env_status, trigger_reset, error_buffer, no_vexpect, no_scorer):
        super(Rewarder, self).__init__(name='Rewarder',)
        self._has_initial_reward = False
        self.reward_parser = None
        self.env = env
        self.vnc_address = vnc_address
        self.agent_conn = agent_conn

        # Imported from EnvController
        self.env_status = env_status
        self.trigger_reset = trigger_reset

        self.daemon = True
        self.error_buffer = error_buffer
        self.no_vexpect = no_vexpect
        self.no_scorer = no_scorer

        self.controlplane_spec = None
        self.set_reward_parser(env_status.env_info())
        self.fps = env_status.fps
        assert self.fps is not None

    def set_reward_parser(self, env_info):
        self.env_id = env_info['env_id']
        self._episode_id = env_info['episode_id']

        # If in demo mode, let the demonstration code know what env is
        # active
        write_env_id(self.env_id)

        if self.env_id is None:
            return
        self.controlplane_spec = gym_controlplane.spec(self.env_id)
        self.spec = gym.spec(self.env_id)

        # This is quite slow (usually 100-200ms) so just be careful
        # about calling it too much. We also have some suspicions that
        # the scorer TF graph may leak memory but haven't needed to
        # investigate.
        self.reward_parser = self.controlplane_spec.build_reward_parser(load_vexpect=not self.no_vexpect, load_scorer=not self.no_scorer)

        # All the pixels needed for vexpect/scoring.
        subscription = self.reward_parser.subscription()
        if subscription is not None:
            subscription = [tuple(sub) for sub in subscription]

        metadata_encoding = self.spec.tags.get('metadata_encoding')
        if metadata_encoding is not None and subscription is not None:
            if metadata_encoding['type'] == 'qrcode':
                subscription += [(metadata_encoding['x'], metadata_encoding['width'], metadata_encoding['y'], metadata_encoding['height'])]
            else:
                raise error.Error('Unsupported metadata encoding type: {}'.format(metadata_encoding))
        # Should fix this up and abstract
        # probe_key = self.spec.tags.get('action_probe')
        probe_key = 0x60

        logger.info('Using metadata_encoding=%s probe_key=%s subscription=%s', metadata_encoding, probe_key, subscription)
        # Just subscribe to the parts of the screen we're going to care about
        self.env.unwrapped.diagnostics.update(
            metadata_encoding=metadata_encoding,
            probe_key=probe_key,
        )
        self.env.unwrapped.vnc_session.update(
            name=self.env.unwrapped.connection_names[0], # hack
            subscription=subscription or [],
        )

    def run(self):
        try:
            self.do_run()
        except Exception as e:
            self.error_buffer.record(e)

    def do_run(self):
        # For debug environments which set a server-enforced time
        # limit
        frames = 0
        # Log all the rewards, but buffer those logs rather than
        # spewing out in realtime.
        reward_logger = remote.RewardLogger()

        last_export = time.time()
        # Just make sure last_export time is set inside of pyprofile
        pyprofile.export(log=False, reset=False)

        # For tracking the framerate
        target = time.time()
        self.__vnc_last_update = target  # real initial value
        while True:
            # Atomically recover details of the env state
            env_info = self.env_status.env_info()
            env_state = env_info['env_state']

            # Hang out until it's all done resetting. We don't need to
            # reset any of our internal state here, as that happens
            # below. (We're not actually guaranteed to actually see a
            # resetting state, if the reset is very fast.)
            while env_state == 'resetting':
                logger.info('[%s] Blocking until env finishes resetting', utils.thread_name())
                env_info = self.env_status.wait_for_env_state_change(env_state)
                logger.info('[%s] Unblocking since env reset finished', utils.thread_name())
                env_state = env_info['env_state']

                # Start our frame timing from here
                target = time.time()

            env_state = env_info['env_state']
            episode_id = env_info['episode_id']
            env_id = env_info['env_id']
            fps = env_info['fps']
            assert env_state == 'running', 'Env state: {}'.format(env_state)

            if fps is not None and fps != self.fps:
                logger.info('[%s] Changing fps: %s -> %s', fps, self.fps, utils.thread_name())
                self.fps = fps

            # Detect whether the environment has reset, and thus we
            # need to clear our internal state.
            if env_id != self.env_id:
                assert episode_id != self._episode_id, 'Episode ids: {}->{}'.format(episode_id, self._episode_id)
                logger.info('[%s] Changing reward_parsers: %s -> %s', utils.thread_name(), self.env_id, env_id)
                # This is slow (since it has to load the scorer), so
                # we call it only in the rare case where the env ID
                # has changed.
                self.set_reward_parser(env_info)
                frames = 0
                reward_logger.reset()
            elif episode_id != self._episode_id and self.reward_parser is None:
                # Just set internal state. This is fast since it
                # doesn't actually have to load anything. Also only
                # relevant during development.
                self.set_reward_parser(env_info)
                frames = 0
                reward_logger.reset()
            elif episode_id != self._episode_id:
                # If the env state ID changed, then we need to reset
                # the reward parser.
                #
                # Not enough just to look whether the env_state is
                # resetting, since in theory we might never see the
                # resetting state for a very fast reset.
                logger.info('[%s] Clearing reward_parser state: env_id=%s episode_id=%s->%s, env_state=%s', utils.thread_name(), env_id, self._episode_id, episode_id, env_state)
                self._episode_id = episode_id
                self.reward_parser.reset()
                frames = 0
                reward_logger.reset()

            # Recover the exact reward
            with pyprofile.push('rewarder.compute_reward'):
                reward, done, info = self.reward()
            # done=None means we're not sure if the game is over or
            # not.
            done = bool(done)

            # Cut short the environment. Currently only used in debug
            # environment.
            if self.controlplane_spec is not None and \
               self.controlplane_spec.server_timestep_limit is not None and \
               frames >= self.controlplane_spec.server_timestep_limit:
                logger.info('[%s] Marking environment as done=True since server_timestep_limit of %d frames reached', utils.thread_name(), frames)
                done = True

            # Add our own statistics
            if time.time() - last_export > 5:
                force_send = True
                last_export = time.time()
                profile = pyprofile.export()
                # Send the pyprofile to the agent. Info keys we set
                # will be available directly to the agent.
                info['rewarder.profile'] = profile
            else:
                force_send = False

            # Send if there's anything interesting to transmit
            if reward != 0 or done or force_send:
                if 'rewarder.profile' in info:
                    # We already print the pyprofile (during the
                    # export) so no need to repeat it here. It's
                    # pretty big.
                    display_info = info.copy()
                    display_info['rewarder.profile'] = '<{} bytes>'.format(len(str(display_info['rewarder.profile'])))
                else:
                    display_info = info

                reward_logger.record(reward, done, info)
                self.agent_conn.send_env_reward(reward, done, info, episode_id=episode_id)

            old_target = target
            # Run at the appropriate frame rate
            target += 1./self.fps

            # Do appropriate sleeping
            delta = target - time.time()
            if done:
                # game_autoresets means the game itself will do the
                # reset, so we don't have to do any work.
                logger.info('[%s] Resetting environment since done=%s', utils.thread_name(), done)
                self.trigger_reset()
            elif delta > 0:
                pyprofile.timing('rewarder.sleep', delta)
                time.sleep(delta)
            else:
                pyprofile.timing('rewarder.sleep.missed', -delta)
                if delta < -0.1:
                    logger.info('[%s] Rewarder fell behind by %ss from target; losing %s frames', utils.thread_name(), -delta, int(-delta * self.fps))
                target = time.time()
            # Record the total time spent in this frame, starting from the top
            pyprofile.timing('rewarder.frame', time.time() - old_target)
            frames += 1

    def reward(self):
        info = {}

        if self.env is None:
            return 0, False, info

        screen, _, done, observation_info = self.env.step([])

        # Copy over the staleness of the observation and the number of
        # VNC updates in the last frame. This gets sent to the client.
        lag = observation_info.get('diagnostics.lag.observation')
        if lag is not None:
            info['rewarder.lag.observation'] = lag[0]
            info['rewarder.lag.observation.timestamp'] = time.time() - lag[0]
        info['rewarder.vnc.updates.n'] = updates_n = observation_info.get('vnc.updates.n')
        info['rewarder.vnc.updates.pixels'] = observation_info.get('vnc.updates.pixels')
        info['rewarder.vnc.updates.bytes'] = observation_info.get('vnc.updates.bytes')

        if updates_n is not None:
            pyprofile.incr('reward.vnc.updates.n', updates_n)

        now = time.time()
        if self._has_initial_reward and info['rewarder.vnc.updates.n'] == 0:  # Nothing new!
            # Timeout after 100 seconds without VNC updates.
            # This means nothing on the screen has changed, which is probably very bad.
            # We log the error and end the episode, hopefully it will recover nicely.
            if now > self._vnc_last_update + 100:
                logger.error('No vnc updates since {}'.format(self._vnc_last_update))
                done = True
            return 0, done, info
        elif self.reward_parser is None:
            return 0, done, info
        self._vnc_last_update = now
        self._has_initial_reward = True

        reward, done, reward_info = self.reward_parser.reward(screen)
        if (self.env_id == 'flashgames.NeonRace2-v0' and reward > 20000) or \
           (self.env_id == 'flashgames.CoasterRacer-v0' and reward > 20000) or \
           (self.env_id == 'internet.SlitherIO-v0' and reward > 1000):
            import tempfile
            f = tempfile.NamedTemporaryFile()
            path = f.name + '.png'
            f.close()

            logger.info('[%s] Abnormally large reward of %s received! This may indicate a bug in the OCR. Saving a screenshot to %s for investigation.', utils.thread_name(), reward, path)
            Image.fromarray(screen).save(path)
        return reward, done, info

class UserInput(threading.Thread):
    def __init__(self, env, env_controller, error_buffer, rewarder):
        super(UserInput, self).__init__(name='UserInput')
        self.instance_id = utils.random_alphanumeric()
        self.env = env
        self.env_controller = env_controller
        self.start_time = None

        self.daemon = True
        self.error_buffer = error_buffer
        self.rewarder = rewarder

    def run(self):
        try:
            self.do_run()
        except Exception as e:
            self.error_buffer.record(e)

    def do_run(self):
        self.start_time = time.time()

        if six.PY2:
            global input
            input = raw_input
        while True:
            try:
                input_command = input("""[UserInput] Input commands:
  t [dump stacktrace]
  i [ipdb session]
  q [quit]
""").strip()
            except EOFError:
                # True when stdin isn't open
                return
            split = input_command.split(' ')
            command, args = split[0], split[1:]

            try:
                if command == 't':
                    self.stacktraces()
                elif command == 'i':
                    import ipdb
                    ipdb.set_trace()
                elif command == 'q':
                    logger.info('[%s] Exiting as requested', utils.thread_name())
                    for proc in manual_subprocess_cleanup.values():
                        proc.kill()
                    os._exit(0)
            except Exception as e:
                if six.PY2:
                    logger.error('[UserInput] Error processing command: %s', traceback.format_exc(e))
                else:
                    logger.error('[UserInput] Error processing command: %s', '\n'.join(traceback.format_exception(type(e), e, e.__traceback__)))

    def stacktraces(self):
        sys.stderr.write("\n*** STACKTRACE - START ***\n")
        code = []
        for threadId, stack in sys._current_frames().items():
            code.append("\n# ThreadID: %s" % threadId)
            for filename, lineno, name, line in traceback.extract_stack(stack):
                code.append('\n>  File: "%s", line %d, in %s' % (filename,
                                                            lineno, name))
                if line:
                    code.append("  %s" % (line.strip()))

        for line in code:
            sys.stderr.write(line)
        sys.stderr.write("\n*** STACKTRACE - END ***\n")

twisty.start_once()

def write_env_id(env_id):
    env_file = '/tmp/demo/env_id.txt'
    if os.path.exists(os.path.dirname(env_file)):
        try:
            with open(env_file, 'w') as f:
                logger.info('[%s] Writing %s to %s', utils.thread_name(), env_id, env_file)
                f.write(env_id or '')
                f.write('\n')
        except PermissionError:
            pass

def main():
    parser = argparse.ArgumentParser(description=None)
    parser.add_argument('-v', '--verbose', action='count', dest='verbosity', default=0, help='Set verbosity.')
    parser.add_argument('-r', '--remotes', default='vnc://127.0.0.1:5900', help='Which VNC address to connect to.')
    parser.add_argument('-e', '--env-id', default=None, help='An env ID to optionally run upon startup (e.g. flashgames.DuskDrive-v0).')
    parser.add_argument('-V', '--no-vexpect', action='store_true', help='Whether to use vexpect.')
    parser.add_argument('-S', '--no-scorer', action='store_true', help='Whether to use the scorer.')
    parser.add_argument('-E', '--no-env', action='store_true', help='Whether to maintain an environment.')
    parser.add_argument('-I', '--integrator-mode', action='store_true', help='Whether to use vexpect.')
    parser.add_argument('-R', '--no-rewarder', action='store_true', help='Whether to enable the rewarder thread at all.')
    parser.add_argument('--rewarder-port', type=int, default=15900, help='Which port to start the agent_conn thread')
    parser.add_argument('--rewarder-fps', default=60, type=float, help='The frame rate for the rewarder.')
    parser.add_argument('-i', '--idle-timeout', type=float, help='How long to keep the environment around when it has no active connections')
    parser.add_argument('--demonstration', action='store_true', help='Run a demonstration agent.')
    parser.add_argument('--bot-demonstration', action='store_true', help='Run a demonstrationa agent that connects to the vnc_recorder port, to record complete demos with no human playing')

    args = parser.parse_args()

    # TODO: only activate in dev
    signal.signal(signal.SIGINT, lambda signal, frame: os._exit(10))

    if args.verbosity == 0:
        logger.setLevel(logging.INFO)
    elif args.verbosity >= 1:
        logger.setLevel(logging.DEBUG)

    # Launch demonstration agent if requested

    if args.bot_demonstration and args.env_id is not None:
        cmd = "/app/universe-envs/controlplane/bin/demonstration_agent.py -e {} -r vnc://localhost:5899+15899 2>&1 | sed -e 's/^/[demonstration_agent] /'".format(pipes.quote(args.env_id))
        logger.info('Launching demonstration agent in bot mode: %s', cmd)
        subprocess.Popen(cmd, shell=True)

    elif args.demonstration and args.env_id is not None:
        cmd = "/app/universe-envs/controlplane/bin/demonstration_agent.py -e {} 2>&1 | sed -e 's/^/[demonstration_agent] /'".format(pipes.quote(args.env_id))
        logger.info('Launching demonstration agent: %s', cmd)
        subprocess.Popen(cmd, shell=True)

    logger.info("Starting play_controlplane.py with the following: command=%s args=%s env=%s", sys.argv, args, os.environ)

    error_buffer = universe.utils.ErrorBuffer()

    env_status = universe.rewarder.EnvStatus()
    env_status.set_env_info(env_id=args.env_id, fps=args.rewarder_fps)

    cv = threading.Condition()
    control_buffer = remote.ControlBuffer(cv)
    agent_conn = remote.AgentConn(env_status, cv, control_buffer, error_buffer=error_buffer, idle_timeout=args.idle_timeout)
    agent_conn.listen(port=args.rewarder_port)

    # Logger gives us the diagnostics printing
    if not args.no_env:
        env = wrappers.Unvectorize(wrappers.Vision(wrappers.Logger(vnc_env.VNCEnv())))
        # Assert when given self-referential rewarder connection
        # This shows up as a '+15900' or similar port number in the remotes string
        assert '+' not in args.remotes, "Remotes may not have rewarder ports"
        env.configure(
            remotes=args.remotes,
            ignore_clock_skew=True,
            disable_action_probes=True,
            vnc_driver='go',
            vnc_kwargs={'encoding': 'zrle', 'compress_level': 9},
            observer=True,
        )
    else:
        logger.info('Running without environment, meaning reward and gameover parsing will be disabled')
        env = None

    no_vexpect = args.no_vexpect or args.integrator_mode

    env_controller = EnvController(
        env, args.remotes, env_status, agent_conn,
        error_buffer=error_buffer, control_buffer=control_buffer,
        no_vexpect=no_vexpect,
        integrator_mode=args.integrator_mode,
    )
    env_controller.start()

    if not args.no_rewarder:
        rewarder = Rewarder(
            env, args.remotes, agent_conn,
            env_status=env_controller.env_status,
            trigger_reset=env_controller.trigger_reset,
            error_buffer=error_buffer, no_vexpect=no_vexpect,
            no_scorer=args.no_scorer,
        )
        rewarder.start()
    else:
        rewarder = None

    manhole.install(locals={'rewarder': rewarder, 'env_controller': env_controller})

    # TODO: clean up this API, but good enough for now
    while True:
        try:
            error_buffer.blocking_check(timeout=60)
        except remote.Exit as e:
            logger.info('%s', e)
            return 0

    return 1

if __name__ == '__main__':
    sys.exit(main())
