import os
import marshal

from .logger import get_logger

LOGGER = get_logger(__name__)


def get_toolset_metadata(root_dir):

    import yaml

    # find .toolset configuration file with all
    # toolset's parameters
    toolset_cfg_path = os.path.join(root_dir, "config.yml")
    if not os.path.isfile(toolset_cfg_path):
        return

    with open(toolset_cfg_path, "r") as f:
        return yaml.load(f)


def execute_file(filepath, globals=None, locals=None):
    if filepath.endswith(".pyc"):
        with open(filepath, "rb") as f:
            f.seek(8)
            code = marshal.load(f)
            exec (code, globals, locals)
    elif filepath.endswith(".py"):
        execfile(filepath, globals, locals)


def resolve(path):
    if not path:
        return path

    return path.replace('\\', '/').replace('/', os.path.sep)