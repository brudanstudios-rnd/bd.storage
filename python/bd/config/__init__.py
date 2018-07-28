import os
import logging
import platform
import cPickle

from .loader import Loader

LOGGER = logging.getLogger("bd.config")


CURRENT_PLATFORM = {
    "Linux": "lin",
    "Windows": "win",
    "Darwin": "mac"
}.get(platform.system())


def load():

    if "BD_OS" not in os.environ:
        os.environ["BD_OS"] = CURRENT_PLATFORM

    base64_config = os.getenv("BD_CONFIG_DATA")

    if base64_config:
        config = cPickle.loads(base64_config.decode("base64", "strict"))
    else:
        config = Loader.load()

        if not config:
            return

        os.environ["BD_CONFIG_DATA"] = cPickle.dumps(config, 2).encode("base64", "strict")

    if "BD_PROJECT" not in os.environ:
        project = config.get("project", {}).get("name")
        if project:
            os.environ["BD_PROJECT"] = project

    return config


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