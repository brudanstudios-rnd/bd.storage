import os
import logging
import platform
import cPickle

from ..logger import get_logger
from .loader import Loader
from ..exceptions import *

LOGGER = get_logger()


CURRENT_PLATFORM = {
    "Linux": "lin",
    "Windows": "win",
    "Darwin": "mac"
}.get(platform.system())

os.environ["BD_OS"] = CURRENT_PLATFORM

_config = None


def load(cached=True, preset=None):

    if not cached:
        return Loader.load(preset)

    global _config

    if _config is None:

        base64_config = os.getenv("BD_CONFIG_DATA")

        if base64_config:
            try:
                _config = cPickle.loads(base64_config.decode("base64", "strict"))
            except Exception:
                raise ConfigDeserializationError(details={"var_name": "BD_CONFIG_DATA"})
        else:
            _config = Loader.load()

            os.environ["BD_CONFIG_DATA"] = cPickle.dumps(_config, 2).encode("base64", "strict")

    return _config


def get_value(key, default=None, config=None, cached=True, preset=None):

    if not config:
        config = load(cached, preset)

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