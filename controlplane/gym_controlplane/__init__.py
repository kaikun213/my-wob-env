import gym
import logging
import os
import sys
import universe

from gym_controlplane.registration import spec, register_task, registry, env_launcher, register_defaults, Task, register_collection

logger = logging.getLogger(__name__)

def logger_setup(prog=None, debug_logfile=True):
    gym.undo_logger_setup()

    if prog is not None:
        infix = '[{}] '.format(prog)
    else:
        infix = '[%(levelname)s:%(name)s] '

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] {}%(message)s'.format(infix))
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    universe.configure_logging(path=False)

    # handler = logging.FileHandler("/tmp/openai.log")
    # handler.setFormatter(formatter)
    # handler.setLevel(logging.DEBUG)
    # logger.addHandler(handler)

# Do this last
import gym_controlplane.includer
