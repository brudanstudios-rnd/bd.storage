__all__ = ["Loader"]

import os
import logging

import metayaml

from ..exceptions import *

LOGGER = logging.getLogger("bd.config.loader")


class Loader(object):

    @classmethod
    def load(cls):
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
                    "configs_dir",
                    "development_dir",
                    "proj_config_dir",
                    "user_config_dir",
                    "git_repo_url_format"):

            if key not in config:
                raise MandatoryKeyNotFoundError(details={"key": key})

            val = config[key]
            if val is None:
                raise ConfigValueTypeError(details={"key": key, "type": type(val)})

        # BD_CONFIG_NAME could be undefined if there was no --config-name option specified
        # in the command line
        if "BD_CONFIG_NAME" in os.environ:
            proj_config_dir = config["proj_config_dir"]
            if not os.path.exists(proj_config_dir):
                raise ProjectConfigurationNotFoundError(details={"config_name": os.environ["BD_CONFIG_NAME"]})

            config_dir = os.path.join(proj_config_dir, "config")
            if not os.path.exists(config_dir):
                raise FilesystemPathNotFoundError(details={"path": config_dir})

            config_search_dirs = [config_dir]

            user_config_dir = os.path.join(config["user_config_dir"], "config")

            if os.path.exists(user_config_dir):
                config_search_dirs.append(user_config_dir)

            # recursively collect all the config file paths
            config_files = []
            for config_search_dir in config_search_dirs:
                for root_dir, _, filenames in os.walk(config_search_dir):
                    for filename in filenames:
                        if not filename.endswith(".yml"):
                            continue
                        config_files.append(os.path.join(root_dir, filename))

            if not config_files:
                raise ProjectConfigFilesNotFound(details={"config_name": os.environ["BD_CONFIG_NAME"]})

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
            config.pop("proj_config_dir", None)
            config.pop("user_config_dir", None)

        config.pop("env", None)

        return config
