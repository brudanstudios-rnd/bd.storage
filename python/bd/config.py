import os
import cPickle

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

join = os.path.join
exists = os.path.exists

LOGGER = get_logger(__name__)

CURRENT_PLATFORM = os.environ["BD_OS"]

_config = None


def _load_config(preset=None):
    pipeline_dir = os.getenv("BD_PIPELINE_DIR")
    if not pipeline_dir:
        raise PipelineNotActivatedError()

    base64_config = os.getenv("BD_CORE_CONFIG_DATA")

    if not base64_config:
        raise ConfigDeserializationError(details={"var_name": "BD_CORE_CONFIG_DATA"})

    try:
        config = cPickle.loads(base64_config.decode("base64", "strict"))
    except Exception as e:
        raise ConfigDeserializationError(details={"var_name": "BD_CORE_CONFIG_DATA"})

    if not preset:
        preset = config.get("current_preset")

    # BD_PRESET_NAME could be undefined if there was no --config-name option specified
    # in the command line
    if preset:

        preset_version = config["presets"].get(preset)

        if preset_version:
            preset_dir = join(os.environ["BD_PRESETS_DIR"], preset, preset_version)
        else:
            preset_dir = join(os.environ["BD_PRESETS_DIR"], preset)

        if not exists(preset_dir):
            raise ProjectPresetNotFoundError(details={"preset_name": preset})

        config["preset_dir"] = preset_dir

        config_file = join(preset_dir, 'config.yml')
        if not exists(config_file):
            raise FilesystemPathNotFoundError(details={"path": config_file})

        config_files = [config_file]

        config_file = join(os.environ["BD_OVERRIDES_DIR"], "config.yml")

        if os.path.exists(config_file):
            config_files.append(config_file)

        if not config_files:
            raise ProjectConfigurationFilesNotFound(details={"preset_name": preset})

        try:
            # read config data
            config.update(
                metayaml.read(
                    config_files,
                    defaults={"env": os.environ.get},
                    extend_key_word="includes"
                )
            )
        except Exception as e:
            raise FailedConfigParsingError(details={"exc_msg": str(e)})

    config.pop("env", None)

    return config


def load(cached=True, preset=None):

    if not cached:
        return _load_config(preset)

    global _config

    if _config is None:

        base64_config = os.getenv("BD_PRESET_CONFIG_DATA")

        if base64_config:
            try:
                _config = cPickle.loads(base64_config.decode("base64", "strict"))
            except Exception:
                raise ConfigDeserializationError(details={"var_name": "BD_PRESET_CONFIG_DATA"})
        else:
            _config = _load_config()

            os.environ["BD_PRESET_CONFIG_DATA"] = cPickle.dumps(_config, 2).encode("base64", "strict")

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