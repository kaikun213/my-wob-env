import logging
import os
import tempfile
import shutil

logger = logging.getLogger(__name__)

def clear_dir(dir):
    # Clear any existing contents
    if os.path.exists(dir):
        target = tempdir_name()
        logger.info('Moving existing %s -> %s', dir, target)
        shutil.move(dir, target)

def tempdir_name():
    dir = tempfile.mkdtemp()
    os.rmdir(dir)
    return dir
