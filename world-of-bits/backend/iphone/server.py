from tornado import web
import random
import os
import six
if six.PY2:
    import urlparse
else:
    import urllib.parse as urlparse
import logging
logger = logging.getLogger()

from backend.server import MockServer
from backend.utils import get_first


global_dictionary = None


def generate_text(min_length=3):
    ''' create an English text with at least min_length.
    '''
    # read dictionary.
    global global_dictionary
    if not global_dictionary:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(dir_path, 'google_20k.txt'), 'r') as f:
            global_dictionary = [word.replace('\n', '') for word in f.readlines()]

    while True:
        word = global_dictionary[random.randint(0, len(global_dictionary))]
        if len(word) >= min_length:
            break

    return word


def compute_reward(post_args, target_args):
    reward = 0.
    for (field, target_value) in target_args.items():
        if field in post_args:
            post_value = post_args[field]
            if post_value == target_value:
                reward += 1.
    return reward


class EnterTextHandler(web.RequestHandler):
    def initialize(self, server):
        self.server = server

    def post(self, request):
        # parse request.
        logger.info('[server] %s request to %s', self.request.method,
                self.request.uri)
        post_args = urlparse.parse_qs(self.request.body)
        post_args = {field.decode('utf-8') : get_first(value)
                     for (field, value) in post_args.items()}
        target_args = self.server.instruction

        # compute reward.
        logger.info('[server] post args = %s', post_args)
        logger.info('[server] target args = %s', target_args)
        reward = compute_reward(post_args, target_args)

        # send back reward.
        self.server.increment_reward(1. + reward) # reward 1 point for submitting.
        self.server.set_done(True)
        self.write({
            'response': 'OK'
        })


class EnterTextServer(MockServer):
    def __init__(self, path):
        super(EnterTextServer, self).__init__(path)
        self.handlers.append(
            (r"(.*)", EnterTextHandler, {"server": self})
        )

        # generate instruction.
        self._generate_instruction()

    def _generate_instruction(self):
        self._instruction = {'text': generate_text(min_length=3)}
        logger.info('instruction = %s', self._instruction)

    @property
    def instruction(self):
        return self._instruction

    def reset(self):
        super(EnterTextServer, self).reset()
        self._generate_instruction()

