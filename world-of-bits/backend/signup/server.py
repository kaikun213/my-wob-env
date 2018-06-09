from tornado import web
import six
if six.PY2:
    import urlparse
else:
    import urllib.parse as urlparse
import logging

logger = logging.getLogger()

from backend.server import MockServer
from backend.signup.instruction import UserProfileTemplate
from backend.utils import get_first


def signup_reward(post_args, target_args):
    reward = 0.
    for (field, target_value) in target_args.items():
        if field in post_args:
            post_value = post_args[field]
            if post_value == target_value:
                reward += 1.
    return reward



class SignupMockHandler(web.RequestHandler):
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
        reward = signup_reward(post_args, target_args)

        # send back reward.
        self.server.increment_reward(1. + reward) # reward 1 point for submitting.
        self.server.set_done(True)
        self.write({
            'response': 'OK'
        })


class SignupMockServer(MockServer):
    def __init__(self, path):
        super(SignupMockServer, self).__init__(path)
        self.handlers.append(
            (r"(.*)", SignupMockHandler, {"server": self})
        )

        # generate instruction.
        self._generate_instruction()

    def _generate_instruction(self):
        template = UserProfileTemplate()
        self._instruction = template.generate()
        logger.info('[server] instruction = %s', self.instruction)

    @property
    def instruction(self):
        return self._instruction

    def reset(self):
        super(SignupMockServer, self).reset()
        self._generate_instruction()

