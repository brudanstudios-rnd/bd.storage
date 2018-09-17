__all__ = ["Loader"]

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

from ..logger import get_logger
from ..exceptions import *
from .. import utils

join = os.path.join
exists = os.path.exists

LOGGER = get_logger(__name__)


class Loader(object):

    @classmethod
    def load(cls, preset=None):
        if "BD_PIPELINE_DIR" not in os.environ:
            raise PipelineNotActivatedError()

        pipeline_dir = utils.resolve(os.environ["BD_PIPELINE_DIR"])
        os.environ["BD_PIPELINE_DIR"] = pipeline_dir

        core_config_path = utils.resolve(os.getenv("BD_CORE_CONFIG_PATH"))
        if not core_config_path:
            # main config file
            core_config_path = join(pipeline_dir, "core.yml")

        if not os.path.exists(core_config_path):
            raise FilesystemPathNotFoundError(details={"path": core_config_path})

        # used to access environment variables inside yaml config files
        defaults = {"env": os.environ.get}

        try:
            # read main config file
            config = metayaml.read(
                core_config_path,
                defaults=defaults,
                extend_key_word="includes"
            )
        except Exception as e:
            raise FailedConfigParsingError(details={"exc_msg": str(e)})

        config["pipeline_dir"] = pipeline_dir

        # check if all the mandatory keys exist
        for key in ("github_account",
                    "github_deploy_repo",
                    "is_centralized"):

            if key not in config:
                raise MandatoryKeyNotFoundError(details={"key": key})

            val = config[key]
            if val is None:
                raise ConfigValueTypeError(details={"key": key, "type": type(val)})

        config["development_dir"] = utils.resolve(os.environ["BD_DEVEL_DIR"])
        config["presets_dir"] = utils.resolve(os.environ["BD_PRESETS_DIR"])
        config["toolbox_dir"] = utils.resolve(os.environ["BD_TOOLBOX_DIR"])

        if not preset:
            preset = os.getenv("BD_PRESET")

        # BD_PRESET could be undefined if there was no --config-name option specified
        # in the command line
        if preset:

            proj_preset_dir = join(config["presets_dir"], preset)

            if not os.path.exists(proj_preset_dir):
                raise ProjectPresetNotFoundError(details={"preset_name": preset})

            config["proj_preset_dir"] = proj_preset_dir

            config_file = join(proj_preset_dir, 'config.yml')
            if not os.path.exists(config_file):
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
                        defaults=defaults,
                        extend_key_word="includes"
                    )
                )
            except Exception as e:
                raise FailedConfigParsingError(details={"exc_msg": str(e)})

            project_name = os.getenv("BD_PROJECT")
            if project_name:
                config["project"] = project_name

        config.pop("env", None)

        return config
