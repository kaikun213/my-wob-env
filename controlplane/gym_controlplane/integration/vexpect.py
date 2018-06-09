import logging
import numpy as np
import os
import six
import time
import yaml

from PIL import Image

from gym.utils import reraise

from universe import utils
from gym_controlplane import error, reward as reward_module
from gym_controlplane.integration import state as state_module, transition as transition_module, utils as integration_utils
from gym_controlplane.utils import join, us

from math import log10, floor, ceil
def round_to_1(x):
    return round(x, -int(floor(log10(abs(x)))))

def suggest_threshold(x):
    multiplier = 10 ** -int(floor(log10(abs(x))))
    suggested = ceil(x * multiplier) / multiplier

    if suggested > 0.7:
        return '{} (probably too large: 0.7 is generally already riskily high)'.format(suggested)
    else:
        return suggested

logger = logging.getLogger()

def or_(ary1, ary2):
    return ary1 | np.array(ary2, dtype=np.bool)

class Dummy(object): pass

class VExpect(object):
    def __init__(self, states, transitions, timeout=None):
        self.states = states
        self.transitions = transitions
        self.timeout = timeout or 60

        self._flag_ipdb = False
        self._flag_debug_show = False
        self._flag_show_score_crop = False

        # Any of these passing means the game is over
        self._gameover_states = self._states_by_stage('gameover')
        # Any of these passing means the game is still running (take
        # precedence over gameover)
        self._running_states = self._states_by_stage('running')
        # Initial states
        self._initial_states = self._states_by_stage('initial')
        # Ready states: active when the game has booted and is ready
        # to play by the agent.
        self._ready_states = self._states_by_stage('ready')

        # No need to double-reset
        self.reset(all=False)

    def reset(self, all=True):
        # Mutable state
        self._gameover_time = None
        self._gameover_count = None
        self._periodic_log = {}

        for state in six.itervalues(self.states):
            state.reset()
        for transition in six.itervalues(self.transitions):
            transition.reset()

    def _states_by_stage(self, stage):
        states = [state for state in six.itervalues(self.states) if state.stage == stage]
        states.sort(key=lambda state: state.state_name)
        return states

    def flag_ipdb(self):
        self._flag_ipdb = True

        while self._flag_ipdb:
            time.sleep(1)

    def flag_debug_show(self):
        self._flag_debug_show = True

        while self._flag_debug_show:
            time.sleep(1)

    def flag_show_score_crop(self):
        self._flag_show_score_crop = True

    @classmethod
    def load(cls, src_dir):
        spec_file = os.path.join(src_dir, 'vexpect.yml')
        with open(spec_file) as f:
            vexpect = yaml.load(f)

        # Just want a mutable message to indicate what was happening
        statehack = Dummy()
        statehack.message = 'getting started'
        try:
            states, transitions = cls._load_data(src_dir, vexpect, statehack)
        except Exception:
            reraise(suffix='(while {} in {})'.format(statehack.message, spec_file))

        timeout = vexpect.get('timeout')
        vexpect = cls(states, transitions, timeout=timeout)
        return vexpect

    @classmethod
    def _load_data(cls, src_dir, vexpect, statehack):
        states = {}
        transitions = {}

        if type(vexpect) == str:
            raise Exception('vexpect.yml is not formatted correctly. Maybe "git lfs pull" failed? vexpect config = "{}"'.format(vexpect))

        for state_name, state_spec in six.iteritems(vexpect['states']):
            statehack.message = 'loading state: {}'.format(state_name)
            state = state_module.State.load(src_dir, state_name, state_spec)
            states[state_name] = state

        for state_name, transition_spec in six.iteritems(vexpect['transitions']):
            statehack.message = 'loading transition from: {}'.format(state_name)
            transition = transition_module.Transition.load(src_dir, state_name, transition_spec)
            transitions[state_name] = transition
        return states, transitions

    def to_spec(self):
        spec = {
            'version': 2,
            'states': {name: state.to_spec() for name, state in six.iteritems(self.states)},
            'transitions': {name: transition.to_spec() for name, transition in six.iteritems(self.transitions)},
        }
        return spec

    def save(self, src_dir):
        integration_utils.clear_dir(src_dir)
        os.makedirs(src_dir)

        # Dump the big files
        for _, state in six.iteritems(self.states):
            state.save(src_dir)

        # Transitions have no assets to save

        spec_file = os.path.join(src_dir, 'vexpect.yml')
        logger.info('Writing vexpect specification: %s', spec_file)
        with open(spec_file, 'w') as f:
            spec = self.to_spec()
            yaml.dump(spec, f)

    def subscribe(self, env, states):
        subscription = []
        for state in states:
            sub = state.subscription
            if sub is None:
                subscription = []
                break
            subscription += sub
        subscription = [tuple(s) for s in subscription]
        env.unwrapped.vnc_session.update(
            name=env.unwrapped.connection_names[0], # hack
            subscription=subscription,
        )

    def run_initialize(self, env, initial_states=None):
        target = time.time()

        # Set of possible start states
        state_changed = True
        old_plausible_states = []

        if initial_states is None:
            # If no initial states, then let's just watch for ready
            # states. Relevant when a game auto-starts, or starts
            # outside of vexpect like Slither
            new_plausible_states = self._initial_states or self._ready_states
        else:
            new_plausible_states = [self.states[state_name] for state_name in initial_states]
        plausible_states = new_plausible_states + old_plausible_states
        self.subscribe(env, plausible_states)

        # Select states which can actually transition
        transitionable_states = [s for s in plausible_states if s.state_name in self.transitions]
        transitionable_states_i = 0

        # No plausible states!
        if len(plausible_states) == 0:
            return

        while True:
            observation, reward, done, info = env.step([])

            if self._flag_ipdb:
                import ipdb
                ipdb.set_trace()
                self._flag_ipdb = False
            if self._flag_debug_show:
                for state in new_plausible_states:
                    state.debug_show(observation)
                    match, info = state.distance(observation)
                    logger.info('%s: distance=%s match=%s', state, info['distance'], match)
                self._flag_debug_show = False

            if state_changed:
                state_changed = False
                start_time = time.time()
                if old_plausible_states:
                    logger.info('Waiting for any of %s to activate (or whether any of %s are still active)', new_plausible_states, old_plausible_states)
                else:
                    logger.info('Waiting for any of %s to activate', new_plausible_states)

            if time.time() - start_time > self.timeout:
                raise error.VExpectTimeout('Error: vexpect has been looking for the same states for {}s: {} (old plausible states: {})'.format(self.timeout, new_plausible_states, old_plausible_states))

            # Do any prep work necessary, such as moving the cursor around
            if len(transitionable_states) > 0:
                hopeful_state = transitionable_states[transitionable_states_i]
                hopeful_transition = self.transitions[hopeful_state.state_name]
                gave_up = hopeful_transition.prepare(env)
                if gave_up and len(transitionable_states) > 1:
                    transitionable_states_i = (transitionable_states_i + 1) % len(transitionable_states)
                    logger.info('Advancing to the next hopeful state (%d/%d): %s', transitionable_states_i+1, len(transitionable_states), transitionable_states[transitionable_states_i])

            active_m = []
            distance_m = []
            match_time_m = []
            for i, state in enumerate(plausible_states):
                start = time.time()
                active, info = state.active(observation, time.time() - start_time)
                active_m.append(active)
                distance_m.append(info['distance'])
                match_time_m.append(time.time()-start)

            utils.periodic_log_debug(self, 'match', 'Attempting to match: plausible_states=%s distance_m=%s match_time_m=%s', join(plausible_states), join(distance_m), us(match_time_m), frequency=5, delay=5)

            if any(active_m):
                i = active_m.index(True)
                state = plausible_states[i]
                match_time = match_time_m[i]

                transition = self.transitions[state.state_name]
                logger.info('Applying transition: %s for active state %s. (Summary: plausible_states=%s distance_m=%s match_time_m=%s)', transition, state, join(plausible_states), join(distance_m), us(match_time_m))
                old_state = i >= len(new_plausible_states)
                if old_state:
                    logger.info('!! State %s is an old state, meaning that our last action failed. This is ok but useful to know.', state)

                if transition is not None:
                    transition.apply(env)

                    # Only advance if this isn't a repeat of an old action
                    if not old_state:
                        state_changed = True
                        # It might not have worked, so keep around the
                        # old plausible states.
                        old_plausible_states = new_plausible_states

                    # Figure out where we might now be!
                    new_plausible_states = [self.states[d] for d in transition.dsts]
                    plausible_states = new_plausible_states + old_plausible_states
                    self.subscribe(env, plausible_states)

                    # Update transitionable states
                    transitionable_states = [s for s in plausible_states if s.state_name in self.transitions]
                    transitionable_states_i = 0

                if state.stage == 'ready':
                    # Woohoo, start stage is active!
                    logger.info('Reaching start state: %s', state)
                    return
                elif not new_plausible_states:
                    # Ran out of initialize states, and there are
                    # no ready states.
                    logger.info('Completed all initialize states')
                    return

            # Throttle to 60 fps
            target += 1/60.
            delta = target - time.time()
            if delta > 0:
                time.sleep(delta)
            else:
                delta = -delta
                if delta > 0.1:
                    logger.info('Fell behind by %ss from target; losing %s frames', delta, int(delta * 60))
                target = time.time()


    # Just for debugging
    def run_gameover(self, env, reward_parser):
        target = time.time()
        last_print = 0
        total_reward = 0

        first_pass = True

        while True:
            observation, reward, done, info = env.step([])
            if reward is not None: total_reward += reward

            if self._flag_ipdb:
                def show(x=0, width=observation.shape[1], y=0, height=observation.shape[0]):
                    Image.fromarray(observation[y:y+height, x:x+width]).show()
                import ipdb
                ipdb.set_trace()
                self._flag_ipdb = False
            if self._flag_debug_show:
                for state in (self._gameover_states + self._running_states):
                    state.debug_show(observation)
                    match, info = state.distance(observation)
                    logger.info('%s: distance=%s match=%s', state, info['distance'], match)
                self._flag_debug_show = False
            if self._flag_show_score_crop:
                self._flag_show_score_crop = False

                if reward_parser.scorer is not None:
                    crop_coords = reward_parser.scorer.crop_coords
                    cropped = reward_module.crop(observation, crop_coords)
                    Image.fromarray(cropped).show()
                else:
                    logger.error('No reward_parser.scorer loaded')

            gameover, info = self.gameover(observation)
            if first_pass:
                first_pass = False

                any_gameover = gameover
                running_distance_n = info['running.distance_n']
                running_match_n = np.array(info['running.distance.match_n'], dtype=np.bool)
                running_active_n = np.array(info['running.active_n'], dtype=np.bool)
                gameover_distance_n = info['gameover.distance_n']
                gameover_match_n = np.array(info['gameover.distance.match_n'], dtype=np.bool)
                gameover_active_n = np.array(info['gameover.active_n'], dtype=np.bool)

            # Aggregate together info from multiple runs
            any_gameover = any_gameover or gameover
            running_distance_n = np.min((running_distance_n, info['running.distance_n']), axis=0)
            running_match_n = or_(running_match_n, info['running.distance.match_n'])
            running_active_n = or_(running_active_n, info['running.active_n'])
            gameover_distance_n = np.min((gameover_distance_n, info['gameover.distance_n']), axis=0)
            gameover_match_n = or_(gameover_match_n, info['gameover.distance.match_n'])
            gameover_active_n = or_(gameover_active_n, info['gameover.active_n'])

            if time.time() - last_print > 1:
                last_print = time.time()
                first_pass = True

                if reward_parser is None or reward_parser.scorer is None: score = None
                else: score = reward_parser.scorer.score(observation)

                logger.info('----------------------')
                logger.info('aggregated for 1s: gameover=%s gameover_distance_n=%s gameover_match_n=%s gameover_active_n=%s (just now: gameover_match_time=%s gameover_elapsed=%0.2f score=%s )',
                            any_gameover,
                            join(gameover_distance_n), join(gameover_match_n), join(gameover_active_n),
                            us(info['gameover.match_time']),
                            info['gameover.elapsed'],
                            score
                )
                if len(running_match_n) > 0:
                    logger.info('aggregated for 1s: running_distance_n=%s running_match_n=%s running_active_n=%s (just now: running_elapsed=%0.2f running_match_time=%s )',
                                join(running_distance_n), join(running_match_n), join(running_active_n),
                                info['running.elapsed'],
                                us(info['running.match_time']))


            # Throttle to 60 fps
            target += 1/60.
            delta = target - time.time()
            if delta > 0:
                time.sleep(delta)
            else:
                delta = -delta
                if delta > 0.1:
                    logger.info('Fell behind by %ss from target; losing %s frames', delta, int(delta * 60))
                target = time.time()

    # Just for debugging
    def run_match(self, env, states):
        distances = np.array([np.inf] * len(states))
        infos = [None] * len(states)
        last_print = 0
        target = time.time()

        while True:
            screen, _, _, _ = env.step([])

            if self._flag_ipdb:
                import ipdb
                ipdb.set_trace()
                self._flag_ipdb = False
            if self._flag_debug_show:
                for state in states:
                    state.debug_show(screen)
                    dist, info = state.distance(screen)
                    logger.info('%s: distance=%s match=%s', state, dist, info['distance.match'])
                self._flag_debug_show = False

            for i, state in enumerate(states):
                match, info = state.distance(screen)
                if info['distance'] < distances[i]:
                    distances[i] = info['distance']
                    infos[i] = info

            if time.time() - last_print > 1:
                logger.info('--------- min distance over last second ---------')
                for state, dist, info in zip(states, distances, infos):
                    if info is None:
                        info = {'distance.match': '(bad matcher: HINT: is one of the crop coordinates negative?)'}
                    logger.info('state=%s distance=%s match=%s', state, dist, info['distance.match'])

                # Clear distances
                last_print = time.time()
                distances[:] = np.inf
                infos = [None] * len(states)

            # Throttle to 60 fps
            target += 1/60.
            delta = target - time.time()
            if delta > 0:
                time.sleep(delta)
            else:
                delta = -delta
                if delta > 0.1:
                    logger.info('Fell behind by %ss from target; losing %s frames', delta, int(delta * 60))
                target = time.time()

    def _active_states(self, states, img, elapsed):
        active_n = []
        distance_n = []
        match_n = []
        warn_n = []

        for state in states:
            active, info = state.active(img, elapsed)
            active_n.append(active)
            distance_n.append(info['distance'])
            match_n.append(info['distance.match'])
            warn_n.append(info['distance.warn'])

        return any(active_n), {
            'distance_n': distance_n,
            'active_n': active_n,
            'distance.match_n': match_n,
            'distance.warn_n': warn_n,
        }

    @property
    def gameover_subscription(self):
        subscription = []
        for state in self._running_states + self._gameover_states:
            sub = state.subscription
            if sub is None:
                return None
            subscription += sub
        return subscription

    # The actual gameover detection method
    def gameover(self, img):
        # Note we don't have an interface for the external world to
        # reset this mutable state. We must create a fresh VExpect to
        # clear the state.
        if self._gameover_time is None: self._gameover_time = time.time()
        running_elapsed = time.time() - self._gameover_time

        start = time.time()
        running, running_info = self._active_states(self._running_states, img, running_elapsed)
        running_match_time = time.time() - start

        # Time since last running state detection. Gameovers with a
        # delay won't trigger if a running state is active.
        if running: self._gameover_time = time.time()
        gameover_elapsed = time.time() - self._gameover_time

        start = time.time()
        gameover, gameover_info = self._active_states(self._gameover_states, img, gameover_elapsed)
        gameover_match_time = time.time() - start

        info = {
            'running': running,
            'running.match_time': running_match_time,
            'running.distance_n': running_info['distance_n'],
            'running.distance.match_n': running_info['distance.match_n'],
            'running.distance.warn_n': running_info['distance.warn_n'],
            'running.active_n': running_info['active_n'],
            'running.elapsed': running_elapsed,

            'gameover': gameover,
            'gameover.match_time': gameover_match_time,
            'gameover.distance_n': gameover_info['distance_n'],
            'gameover.distance.match_n': gameover_info['distance.match_n'],
            'gameover.distance.warn_n': gameover_info['distance.warn_n'],
            'gameover.active_n': gameover_info['active_n'],
            'gameover.elapsed': gameover_elapsed,
        }

        (warn_idxs, ) = np.where(info['gameover.distance.warn_n'])
        if not gameover and len(warn_idxs) > 0:
            states = [self._gameover_states[i] for i in warn_idxs]
            thresholds = [s.match_threshold for s in states]
            distances = [info['gameover.distance_n'][i] for i in warn_idxs]
            suggested_thresholds = [suggest_threshold(d) for d in distances]

            utils.periodic_log(self, 'gameover_warnings', 'Something close to gameover screen detected: warn_n=%s distance_n=%s. Consider increasing the match_threshold for %s from %s to %s', info['gameover.distance.warn_n'], join(info['gameover.distance_n']), join(states), join(thresholds), join(suggested_thresholds))

        if running and not gameover:
            if any(info['gameover.distance.match_n']):
                utils.periodic_log(self, 'gameover_distance_warnings', 'The running state is active, and a gameover state matched. The game will continue running, but this may mean your gamover threshold is too high: gameover.distance.match_n=%s', join(info['gameover.distance.match_n']), frequency=5)

            # Pretty uninteresting: we're running but the game isn't over
            return False, info
        elif running:
            assert gameover
            # Ok, this is interesting
            utils.periodic_log(self, 'gameover_and_running', 'Gameover and running states both triggered. The game will assume it is still running. This is not harmful, but undesirable. Please tune the running and gameover states so they cannot be active at once: %s', info)
            return False, info
        elif gameover:
            utils.periodic_log(self, 'gameover', 'Gameover screen detected: distance_n=%s match_time=%s', join(info['gameover.distance_n']), us(info['gameover.match_time']))
            if self._running_states:
                utils.periodic_log(self, 'running', '(Running state was not triggered: distance_n=%s match_time=%s )', join(info['running.distance_n']), us(info['running.match_time']))

            return True, info
        else:
            if len(self._running_states):
                utils.periodic_log(self, 'no_running', 'Neither running nor gameover states are triggered: running.distance_n=%s running.match_time=%s but neither was gameover: gameover.distance_n=%s gameover.match_time=%s', join(info['running.distance_n']), us(info['running.match_time']), join(info['gameover.distance_n']), us(info['gameover.match_time']), frequency=30)

            return False, info

    def __repr__(self):
        return str(self)

    def __str__(self):
        return 'VExpect<{}>'.format(self.transitions, self.states)
