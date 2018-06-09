import logging
import numpy as np
import os
import re
import six
import yaml

from PIL import Image
from gym_controlplane.integration import utils, vexpect

logger = logging.getLogger(__name__)

class VExpectWriter(object):
    def __init__(self, src_dir, merge=False):
        self.src_dir = src_dir
        self._state_ids = {}

        self.images = []
        self.states = {}
        self.transitions = {}

        self.ordered_states = []

        self.metadata = {}

        if src_dir is not None and merge:
            existing = vexpect.VExpect.load(src_dir)
            self.states = existing.states
            self.transitions = existing.transitions
            # self.ordered_states = sorted(self.states.values(), key=lambda state: (state.state_category, state.state_id))
            for state in six.itervalues(self.states):
                self._state_ids[state.state_category] = max(
                    self._state_ids.get(state.state_category, -1),
                    state.state_id,
                )
        elif src_dir is not None:
            utils.clear_dir(src_dir)
            os.makedirs(src_dir)

    def _path(self, *args):
        return os.path.abspath(os.path.join(self.src_dir, *args))

    def next_state_name(self, base):
        self._state_ids.setdefault(base, -1)
        self._state_ids[base] += 1
        return '{}{}'.format(base, self._state_ids[base])

    def add_image(self, name, img):
        # logger.info('Adding new image: %s', name)
        self.images.append({'name': name, 'contents': img})

    def add_state(self, state, timestamp):
        logger.info('Adding new state: %s (timestamp: %s)', state.state_name, timestamp)
        self.metadata.setdefault('states', {})[state.state_name] = {
            'timestamp': timestamp,
        }

        self.states[state.state_name] = state
        self.ordered_states.append(state)

    def add_transition(self, state_name, transition):
        logger.info('Adding new transition: %s (%s)', transition.transition_name, transition)

        self.transitions[state_name] = transition

    def to_spec(self):
        states = {}
        transitions = {}

        for state_name, state in six.iteritems(self.states):
            states[state_name] = state.to_spec()

        for state_name, transition in six.iteritems(self.transitions):
            transitions[state_name] = transition.to_spec()

        return {
            'states': states,
            'transitions': transitions,
            'metadata': self.metadata,
        }

    def save(self):
        if self.src_dir is None:
            logger.info('Not writing anything since no src_dir provided. Would have written %d image files.', len(self.images))
            logger.info('Would have written the following spec: %s', self.to_spec())
            return

        for image_spec in self.images:
            path = self._path(image_spec['name'])
            contents = image_spec['contents']
            write_png(path, contents)

        with open(self._path('vexpect.yml'), 'w') as f:
            spec = self.to_spec()
            yaml.dump(spec, f)

def write_png(target, contents):
    contents = Image.fromarray(contents)
    contents.save(target, 'png')
