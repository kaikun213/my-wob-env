import base64
import os
import threading
import uuid

from PIL import Image

from gym_controlplane import error

def imread(path):
    import cv2
    if not os.path.exists(path):
        raise error.Error('Image path does not exist: {}'.format(path))
    return cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)

def imshow(ary):
    Image.fromarray(ary).show()

def thread_name():
    return threading.current_thread().name

def random_alphanumeric(length=14):
    buf = []
    while len(buf) < length:
        entropy = str(base64.encodestring(uuid.uuid4().bytes))
        bytes = [c for c in entropy if c.isalnum()]
        buf += bytes
    return ''.join(buf[:])

import pipes
def pretty_command(command):
    return ' '.join(pipes.quote(c) for c in command)

def us(f):
    if isinstance(f, list):
        return join([us(e) for e in f])
    else:
        return '{}us'.format(int(1000 * 1000 * f))

def join(l):
    if len(l) == 1:
        return l[0]
    else:
        return l

import pkg_resources
# copied from gym
def load(name):
    entry_point = pkg_resources.EntryPoint.parse('x={}'.format(name))
    result = entry_point.load(False)
    return result
