from __future__ import print_function
from tornado import (ioloop, web)
import argparse
import six
if six.PY2:
    import urlparse
else:
    import urllib.parse as urlparse
import os
import threading

MOCK_PORT = 8081

class MockHandler(web.RequestHandler):
    def initialize(self, post_callback=None):
        ''' initialize the MockHandler with some args.
        post_callback - called with arguemnts for a given POST request.
        '''
        self.post_callback = post_callback

    def post(self, request):
        print('[post] %s request to %s', self.request.method,
                self.request.uri)
        args = urlparse.parse_qs(self.request.body)
        print('args', args)
        if self.post_callback:
            self.post_callback(args)

    def get(self, request):
        return


class MockServer(object):
    '''
    A server has global state
        WOB_REWARD_GLOBAL - the server-side reward.
        WOB_DONE_GLOBAL - the server-side done signal.
    '''
    def __init__(self, path):
        self.path = path
        self.settings = {
            "autoreload": True,
            "debug": True,
            "template_path": "."
        }

        self.handlers = [
            (r"/", web.RedirectHandler, {"url": "/index.html"}),
            (r"/(.*\.html)", web.StaticFileHandler, {"path": self.path}),
            (r"/(.*\.jpg)", web.StaticFileHandler, {"path": self.path}),
            (r"/(.*\.png)", web.StaticFileHandler, {"path": self.path}),
            (r"/(.*\.css)", web.StaticFileHandler, {"path": self.path}),
            (r"/(.*\.js)", web.StaticFileHandler, {"path": self.path}),
        ]

        self.http_server = None

        # initialize global states.
        self.WOB_LOCK = threading.Lock()
        self.WOB_REWARD_GLOBAL = 0
        self.WOB_DONE_GLOBAL = False

    # TODO: change (reward, done) atomically.
    def increment_reward(self, value):
        self.WOB_LOCK.acquire()
        self.WOB_REWARD_GLOBAL += value
        self.WOB_LOCK.release()

    def set_done(self, done_flag=True):
        self.WOB_LOCK.acquire()
        self.WOB_DONE_GLOBAL = done_flag
        self.WOB_LOCK.release()

    def start(self):
        self.app = web.Application(self.handlers, **self.settings)
        self.http_server = self.app.listen(MOCK_PORT, address="0.0.0.0")

    def stop(self):
        self.http_server.stop()

    def reset(self):
        self.stop()
        self.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='launch a mock server for frontend component')
    parser.add_argument('path', type=str)
    args = parser.parse_args()

    mock_server = MockServer(args.path)
    mock_server.start()
    print('mock server started')
    ioloop.IOLoop.current().start()
