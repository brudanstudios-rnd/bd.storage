import os
import logging
import platform
import cPickle

from .loader import Loader
from ..exceptions import *

LOGGER = logging.getLogger(__name__)


CURRENT_PLATFORM = {
    "Linux": "lin",
    "Windows": "win",
    "Darwin": "mac"
}.get(platform.system())


_config = None


def load():

    global _config

    if _config is not None:
        return _config

    if "BD_OS" not in os.environ:
        os.environ["BD_OS"] = CURRENT_PLATFORM

    base64_config = os.getenv("BD_CONFIG_DATA")

    if base64_config:
        try:
            _config = cPickle.loads(base64_config.decode("base64", "strict"))
        except Exception:
            raise ConfigDeserializationError(details={"var_name": "BD_CONFIG_DATA"})
    else:
        _config = Loader.load()

        os.environ["BD_CONFIG_DATA"] = cPickle.dumps(_config, 2).encode("base64", "strict")

    if "BD_PROJECT" not in os.environ and "project" in _config:
        os.environ["BD_PROJECT"] = _config["project"]

    return _config


def get_value(key, default=None):

    config = load()

    keys = key.strip().split("/")

    if not keys:
        return default

    try:
        for key in keys:
            if not key:
                continue
            config = config[key]
    except:
        return default

    if isinstance(config, dict):
        if CURRENT_PLATFORM in config:
            config = config[CURRENT_PLATFORM]

    return config