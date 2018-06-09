# users should symlink in any files that should be loaded
import glob
import os

modules = glob.glob(os.path.join(os.path.dirname(__file__), '*.py'))
__all__ = [os.path.basename(f)[:-len('.py')] for f in modules]
