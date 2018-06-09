# Used inside of the docker container
from gym_controlplane.include import *

import imp
import os
import glob
# Used outside of the docker container
modules = glob.glob(os.path.join(os.path.dirname(__file__), '../../vnc-private-controlplane/*.py'))
for module in modules:
    if not os.path.exists(module):
        # broken symlink
        continue
    imp.load_source('gym_controlplane.dummy', module)
