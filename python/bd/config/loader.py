__all__ = ["Loader"]

import os
import logging

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


from ..exceptions import *


LOGGER = logging.getLogger(__name__)


class Loader(object):

    @classmethod
    def load(cls, preset_name=None):
        if "BD_PIPELINE_DIR" not in os.environ:
            raise PipelineNotActivatedError()

        # main config file
        core_config_path = os.path.join(os.environ["BD_PIPELINE_DIR"], "core.yml")

        if not os.path.exists(core_config_path):
            raise FilesystemPathNotFoundError(details={"path": core_config_path})

        environ = os.environ.copy()
        environ["BD_PIPELINE_DIR"] = environ["BD_PIPELINE_DIR"].replace('\\', '/')

        # used to access environment variables inside yaml config files
        defaults = {"env": environ.get}

        try:
            # read main config file
            config = metayaml.read(
                core_config_path,
                defaults=defaults,
                extend_key_word="includes"
            )
        except Exception as e:
            raise FailedConfigParsingError(details={"exc_msg": str(e)})

        # check if all the mandatory keys exist
        for key in ("pipeline_dir",
                    "presets_dir",
                    "development_dir",
                    "proj_preset_dir",
                    "user_overrides_dir",
                    "github_account",
                    "github_deploy_repo",
                    "is_centralized"):

            if key not in config:
                raise MandatoryKeyNotFoundError(details={"key": key})

            val = config[key]
            if val is None:
                raise ConfigValueTypeError(details={"key": key, "type": type(val)})

        if not preset_name:
            preset_name = os.getenv("BD_PRESET_NAME")

        # BD_PRESET_NAME could be undefined if there was no --config-name option specified
        # in the command line
        if preset_name:
            proj_preset_dir = config["proj_preset_dir"]
            if not os.path.exists(proj_preset_dir):
                raise ProjectPresetNotFoundError(details={"preset_name": preset_name})

            config_dir = os.path.join(proj_preset_dir, "config")
            if not os.path.exists(config_dir):
                raise FilesystemPathNotFoundError(details={"path": config_dir})

            config_search_dirs = [config_dir]

            user_overrides_dir = os.path.join(config["user_overrides_dir"], "config")

            if os.path.exists(user_overrides_dir):
                config_search_dirs.append(user_overrides_dir)

            # recursively collect all the config file paths
            config_files = []
            for config_search_dir in config_search_dirs:
                for root_dir, _, filenames in os.walk(config_search_dir):
                    for filename in filenames:
                        if not filename.endswith(".yml"):
                            continue
                        config_files.append(os.path.join(root_dir, filename))

            if not config_files:
                raise ProjectConfigurationFilesNotFound(details={"preset_name": preset_name})

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

            if "project" not in config:
                raise MandatoryKeyNotFoundError(details={"key": "project"})
        else:
            config.pop("proj_preset_dir", None)
            config.pop("user_overrides_dir", None)

        if "BD_DEVEL_DIR" in os.environ:
            config["development_dir"] = os.getenv("BD_DEVEL_DIR").replace("\\", "/")

        config.pop("env", None)

        return config
