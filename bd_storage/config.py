import os

import metayaml

myml = metayaml.metayaml


def construct_mapping(self, node, deep=False):
    """Enforce all numeric keys to become strings."""
    data = self.construct_mapping_org(node, deep)
    return myml.OrderedDict([
        (
            str(key) if isinstance(key, (int, float)) else key,
            data[key]
        ) for key in data
    ])


myml.OrderedDictYAMLLoader.construct_mapping_org = myml.OrderedDictYAMLLoader.construct_mapping
myml.OrderedDictYAMLLoader.construct_mapping = construct_mapping

from .logger import get_logger
from .exceptions import *
from . import utils

join = os.path.join
exists = os.path.exists

LOGGER = get_logger(__name__)

CURRENT_PLATFORM = os.environ.get("BD_OS")

_config = None


def _load_config(preset_dir=None):
    if not preset_dir:
        active_preset_info = utils.get_active_preset_info()

        if not active_preset_info:
            raise Error("Unable to get active preset info.")

        preset_dir = active_preset_info["dirname"]

    config_file = join(preset_dir, 'config.yml')
    if not exists(config_file):
        raise Error('Unable to find a preset configuration file')

    try:
        # read config data
        config = metayaml.read(
            config_file,
            defaults={"env": os.environ.get},
            extend_key_word="includes"
        )
    except Exception as e:
        raise Error('Unable to parse the preset configuration file. {}'.format(e))

    config.pop("env", None)

    return config


def load(cached=True, preset_dir=None):

    if not cached:
        return _load_config(preset_dir)

    global _config

    if _config is None:
        _config = _load_config()

    return _config


def get_value(key, default=None, config=None, cached=True, preset_dir=None):

    if not config:
        config = load(cached, preset_dir)

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