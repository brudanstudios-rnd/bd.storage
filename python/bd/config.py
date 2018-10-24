import os
import cPickle

import yaml
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
    pipeline_dir = os.getenv("BD_PIPELINE_DIR")
    if not pipeline_dir:
        raise PipelineNotActivatedError()

    if not preset_dir:
        active_preset_info = utils.get_active_preset_info()

        if not active_preset_info:
            raise Exception("Unable to get active preset info.")

        preset_dir = active_preset_info["dirname"]

    config_file = join(preset_dir, 'config.yml')
    if not exists(config_file):
        raise FilesystemPathNotFoundError(details={"path": config_file})

    config_files = [config_file]

    config_file = join(os.environ["BD_OVERRIDES_DIR"], "config.yml")

    if os.path.exists(config_file):
        config_files.append(config_file)

    if not config_files:
        raise ProjectConfigurationFilesNotFound(details={"preset_dir": preset_dir})

    try:
        # read config data
        config = metayaml.read(
            config_files,
            defaults={"env": os.environ.get},
            extend_key_word="includes"
        )
    except Exception as e:
        raise FailedConfigParsingError(details={"exc_msg": str(e)})

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


def set_override_value(key, value):
    config_file = join(os.environ["BD_OVERRIDES_DIR"], "config.yml")

    config_data = {}

    if exists(config_file):
        with open(config_file, "r") as f:
            config_data = yaml.safe_load(f) or {}

    keys = key.strip().split("/")
    num_keys = len(keys)

    parent_branch = config_data

    for i, key in enumerate(keys, start=1):

        if not key:
            continue

        nested_branch = parent_branch.get(key)

        if i == num_keys:
            if nested_branch:
                if isinstance(nested_branch, dict):
                    raise Error(
                        "Unable to add an override '{}'. Overwriting the "
                        "configuration branch '{}' is not an acceptable "
                        "operation.".format(
                            '/'.join(keys),
                            '/'.join(keys[:i])
                        )
                    )

            parent_branch[key] = value
        else:
            if nested_branch:
                if not isinstance(nested_branch, dict):
                    raise Error(
                        "Unable to add an override '{}'. Overwriting the "
                        "configuration branch '{}' is not an acceptable "
                        "operation.".format(
                            '/'.join(keys),
                            '/'.join(keys[:i])
                        )
                    )
            else:
                nested_branch = {}

            parent_branch[key] = nested_branch
            parent_branch = nested_branch

    with open(config_file, "w") as f:
        yaml.safe_dump(config_data, f, default_flow_style=False)


if __name__ == '__main__':
    os.environ["BD_OVERRIDES_DIR"] = "D:/bd-test-storage/overrides"

    set_override_value(
        "launchers/houdini/16.5.496/win",
        '"C:/Program Files/Side Effects Software/Houdini 16.5.496/bin/houdinifx.exe"'
    )