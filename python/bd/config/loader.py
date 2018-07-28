__all__ = ["Loader"]

import os
import logging

import metayaml

from ..exceptions import *

LOGGER = logging.getLogger("bd.config.loader")


class Loader(object):

    @classmethod
    def load(cls):
        # main config file
        core_config_path = os.path.join(os.environ["BD_PIPELINE_DIR"], "core.yml")

        if not os.path.exists(core_config_path):
            raise BDFilesystemPathNotFound(core_config_path)

        # used to access environment variables inside yaml config files
        defaults = {"env": os.getenv}

        try:
            # read main config file
            config = metayaml.read(
                core_config_path,
                defaults=defaults,
                extend_key_word="includes"
            )
        except Exception as e:
            raise BDFailedConfigParsing(str(e))

        # check if all the mandatory keys exist
        for var in ("pipeline_dir",
                    "configs_dir",
                    "development_dir",
                    "proj_config_dir",
                    "user_config_dir",
                    "git_repo_url_format"):
            if var not in config:
                raise BDMandatoryKeyNotFound(var)

        if "BD_CONFIG_NAME" in os.environ:
            proj_config_dir = config["proj_config_dir"]
            if not os.path.exists(proj_config_dir):
                raise BDProjectConfigurationNotFound(os.environ["BD_CONFIG_NAME"])

            config_dir = os.path.join(proj_config_dir, "config")
            if not os.path.exists(config_dir):
                raise BDFilesystemPathNotFound(config_dir)

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

            # read config data
            config.update(
                metayaml.read(
                    config_files,
                    defaults=defaults,
                    extend_key_word="includes"
                )
            )

        config.pop("env")

        return config
