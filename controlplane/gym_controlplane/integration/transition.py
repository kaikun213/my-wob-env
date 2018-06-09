import logging
import time

from universe import spaces
from gym_controlplane import error

logger = logging.getLogger(__name__)

class Transition(object):
    @classmethod
    def load(cls, src_dir, src, spec):
        if isinstance(spec, list):
            transitions = [cls.from_spec(src_dir, src, t) for t in spec]
            return TransitionList(transitions)
        type = spec.pop('type')
        if type == 'ClickTransition':
            return ClickTransition(src, **spec)
        elif type == 'KeyPressTransition':
            return KeyPressTransition(src, **spec)
        elif type == 'DragTransition':
            return DragTransition(src, **spec)
        else:
            raise error.Error('Bad transition type: {}'.format(spec['type']))

class TransitionList(object):
    def __init__(self, transitions):
        self.transitions = transitions
        self.dsts = transitions[-1].dsts

    def prepare(self, env):
        self.transitions[0].prepare(env)

    def apply(self, env):
        for transition in self.transitions:
            transition.apply(env)


class DragTransition(object):
    def __init__(self, src, dsts, x, y, buttonmask, drag_from_x, drag_from_y, drag_from_buttonmask):
        self.src = src
        self.dsts = dsts

        self.x = x
        self.y = y
        self.buttonmask = buttonmask

        self.drag_from_x = drag_from_x
        self.drag_from_y = drag_from_y
        self.drag_from_buttonmask = drag_from_buttonmask

        self.transition_name = '{}->{}'.format(self.src, self.dsts)
        self.reset()

    def reset(self):
        # Mutable state
        self._drag_start_time = None
        self.i = 0

        self._wait_time = .75
        self._drag_time = .5
        self._drag_tries = 2

    def prepare(self, env):
        if self._drag_start_time is None:
            self._drag_start_time = time.time()
        delta = time.time() - self._drag_start_time
        if delta < self._wait_time:
            return
        delta -= self._wait_time

        weight = delta/self._drag_time
        if weight > 1:
            self.i += 1
            # Give up if we've exceeded our number of tries
            give_up = self.i >= self._drag_tries
            if give_up:
                self.reset()
            else:
                self._drag_start_time = None
            return give_up

        x = int(weight * self.x + (1-weight) * self.drag_from_x)
        y = int(weight * self.y + (1-weight) * self.drag_from_y)
        buttonmask = self.drag_from_buttonmask

        action = [spaces.PointerEvent(x, y, buttonmask)]
        env.step(action)

    def apply(self, env):
        apply = [spaces.PointerEvent(self.x, self.y, self.drag_from_buttonmask),
                 spaces.PointerEvent(self.x, self.y, self.buttonmask)]
        env.step(apply)

    def __str__(self):
        return 'DragTransition<{} x={} y={} buttonmask={} drag_from_x={} drag_from_y={} drag_from_buttonmask={}>'.format(self.transition_name, self.x, self.y, self.buttonmask, self.drag_from_x, self.drag_from_y, self.drag_from_buttonmask)

    def to_spec(self):
        spec = {
            'type': 'DragTransition',
            'x': self.x,
            'y': self.y,
            'buttonmask': self.buttonmask,
            'drag_from_x': self.drag_from_x,
            'drag_from_y': self.drag_from_y,
            'drag_from_buttonmask': self.drag_from_buttonmask,
        }
        if self.dsts: spec['dsts'] = self.dsts
        return spec

class ClickTransition(object):
    def __init__(self, src, x, y, dsts=None, buttonmask=None, hold_after=None, hold_between=None, is_drag=False):
        if dsts is None: dsts = []
        if buttonmask is None: buttonmask = 0
        if hold_after is None: hold_after = 0

        self.src = src
        self.dsts = dsts

        self.x = x
        self.y = y
        self.buttonmask = buttonmask

        self.is_drag = False

        self.transition_name = '{}->{}'.format(self.src, self.dsts)

        # Move mouse back and forth every second in order to trigger
        # hover state.
        self._prepares = [
            [spaces.PointerEvent(x+1, y)],
            [spaces.PointerEvent(x, y)],
            # Probably not completely off-screen but outside of
            # whatever button is active
            [spaces.PointerEvent(25, 100)],
        ]

        self._apply_down = [spaces.PointerEvent(x, y, buttonmask)]
        if self.is_drag:
            self._apply_up = []
        else:
            self._apply_up = [spaces.PointerEvent(x, y)]
        self.hold_after = hold_after
        self.hold_between = hold_between

        self.reset()

    def reset(self):
        # Mutable state
        self._last_prepare = 0
        self._prepare_i = 1
        self._printed = False

    def prepare(self, env):
        if time.time() - self._last_prepare < 1:
            return
        self._last_prepare = time.time()

        action = self._prepares[self._prepare_i % 3]

        env.step(action)
        self._prepare_i += 1
        # 2 cycles -- let someone else have a turn
        if self._prepare_i == 3 * 2:
            self._prepare_i = 0
            return True

    def apply(self, env):
        # logger.info('Applying transition %s: %s', self.transition_name, self._apply)
        if self.hold_between is None:
            # Could do two steps just as well. Two steps will probably
            # work in strictly more cases than one, so we stick with
            # one for now.
            env.step(self._apply_down + self._apply_up)
        else:
            env.step(self._apply1)
            time.sleep(self.hold_between)
            env.step(self._apply2)
        if self.hold_after:
            time.sleep(self.hold_after)

    def __str__(self):
        return 'ClickTransition<{} x={} y={} buttonmask={}>'.format(self.transition_name, self.x, self.y, self.buttonmask)

    def to_spec(self):
        spec = {
            'type': 'ClickTransition',
            'x': self.x,
            'y': self.y,
        }
        if self.buttonmask != 0: spec['buttonmask'] = self.buttonmask
        if self.dsts: spec['dsts'] = self.dsts
        if self.is_drag: spec['is_drag'] = self.is_drag
        return spec

class KeyPressTransition(object):
    def __init__(self, src, dsts, key):
        self.src = src
        self.dsts = dsts
        self.key = key

        self.transition_name = '{}->{}'.format(self.src, self.dsts)

        # Press key quickly
        self._apply = [spaces.KeyEvent(key, down=True), spaces.KeyEvent(key, down=False)]

    def prepare(self, env):
        # Always let someone else have a turn. No prep work to be done.
        return True

    def apply(self, env):
        logger.info('Running VNC events for %s: %s', self.transition_name, self._apply)
        env.step(self._apply)

    def reset(self):
        pass

    def __str__(self):
        return 'KeyPressTransition<key={}>'.format(self.key)

    def to_spec(self):
        spec = {
            'type': 'KeyPressTransition',
            'key': self.key,
        }
        if self.dsts: spec['dsts'] = self.dsts
        return spec
