__all__ = ["Loader"]

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

from ..logger import get_logger
from ..exceptions import *

join = os.path.join
exists = os.path.exists

LOGGER = get_logger(__name__)


class Loader(object):

    @classmethod
    def load(cls, preset=None):
        if "BD_PIPELINE_DIR" not in os.environ:
            raise PipelineNotActivatedError()

        base64_config = os.getenv("BD_CORE_CONFIG_DATA")

        if not base64_config:
            raise ConfigDeserializationError(details={"var_name": "BD_CORE_CONFIG_DATA"})

        try:
            config = cPickle.loads(base64_config.decode("base64", "strict"))
        except Exception as e:
            raise ConfigDeserializationError(details={"var_name": "BD_CORE_CONFIG_DATA"})

        if not preset:
            preset = os.getenv("BD_PRESET")

        # BD_PRESET could be undefined if there was no --config-name option specified
        # in the command line
        if preset:

            proj_preset_dir = os.getenv("BD_PRESET_DIR")

            if not proj_preset_dir:

                preset_version = config.get("presets", {}).get(preset)

                if preset_version:
                    proj_preset_dir = join(config["presets_dir"], preset, preset_version)
                else:
                    proj_preset_dir = join(config["presets_dir"], preset)

                if not exists(proj_preset_dir):
                    raise ProjectPresetNotFoundError(details={"preset_name": preset})

            config["proj_preset_dir"] = proj_preset_dir

            config_file = join(proj_preset_dir, 'config.yml')
            if not exists(config_file):
                raise FilesystemPathNotFoundError(details={"path": config_file})

            config_files = [config_file]

            config_file = join(proj_preset_dir, "overrides", os.environ["BD_USER"], "config.yml")

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
