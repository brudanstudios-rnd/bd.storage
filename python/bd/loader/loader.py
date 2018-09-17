# -*- coding: utf-8 -*-
__all__ = ["load_toolsets", "list_toolsets", "get_available_toolsets"]

import os
import logging

from ..logger import get_logger
from .. import config
from .. import hooks
from .. import installer
from .environment import ENV
from .. import utils


LOGGER = get_logger(__name__)


def _execute_bd_init(directory):

    init_path = os.path.join(directory, "bd_init.py")

    if not os.path.exists(init_path):
        init_path = os.path.join(directory, "bd_init.pyc")

        if not os.path.exists(init_path):
            return

    LOGGER.debug("Calling initializer '{}'".format(init_path))

    CWD = directory

    try:
        utils.execute_file(init_path, globals(), locals())
    except Exception:
        LOGGER.exception("Unable to execute initializer due to an error:")


def _load_app_environment(toolset_dir, app_name, app_version):

    # find a directory inside the toolset for the specified app
    # e.g. houdini, maya, ...
    app_dir = os.path.join(toolset_dir, app_name)
    if not app_dir or not os.path.isdir(app_dir):
        return

    # every app directory stores a version of the
    # matching application version
    # e.g. 2018, 16.0.736, ...
    app_dir_versions = sorted(os.listdir(app_dir), reverse=True)

    if not app_dir_versions:
        LOGGER.error("Unable to find any versioned "
                     "sub-directory in '{}'".format(app_dir))
        return

    # execute initializer inside app directory
    _execute_bd_init(app_dir)

    app_version_dir = None

    if app_version:
        app_version_dir = os.path.join(app_dir, app_version)

    if not app_version_dir or not os.path.exists(app_version_dir):
        app_version_dir = os.path.join(app_dir, app_dir_versions[0])

    hooks.execute("bd.loader.initialize.{}".format(app_name), app_version_dir, ENV).all()

    _execute_bd_init(app_version_dir)


def _load_python_environment(toolset_dir):

    # find a 'python' directory inside the toolset
    python_dir = os.path.join(toolset_dir, "python")
    if not os.path.isdir(python_dir):
        return

    # execute initializer inside app directory
    _execute_bd_init(python_dir)

    hooks.execute("bd.loader.initialize.python", python_dir, ENV).all()


def _check_dependencies(toolset_name, toolset_dir, all_toolset_names):
    toolset_metadata = utils.get_toolset_metadata(toolset_dir)
    if not toolset_metadata:
        return

    required_toolsets = toolset_metadata.get("required")

    if not required_toolsets:
        return

    missing_toolsets = list(set(required_toolsets).difference(all_toolset_names))

    if missing_toolsets:
        LOGGER.warning("Toolset '{}' has missing dependencies: "
                       "{}".format(toolset_name, ', '.join(missing_toolsets)))
        return missing_toolsets


def get_available_toolsets(devel=False):
    # configuration that tells us which toolsets to load
    #
    toolbox_cfg_toolsets = config.get_value("toolbox")
    if not toolbox_cfg_toolsets:
        LOGGER.warning("Configuration 'toolbox' is not defined")
        return

    # a list of tuples [(toolset_name, toolset_version, toolset_dir), ...]
    toolsets_to_load = []

    # locate all the toolsets specified in the configuration
    #
    for toolset_name, toolset_config in toolbox_cfg_toolsets.iteritems():

        toolset_dir = None
        toolset_version = "devel"

        if devel:
            development_dir = utils.resolve(config.get_value("development_dir"))
            devel_toolset_dir = os.path.join(development_dir, "toolbox", toolset_name)
            if os.path.exists(devel_toolset_dir):
                toolset_dir = devel_toolset_dir

        if not toolset_dir:

            toolset_version = toolset_config.get("version")
            if not toolset_version:
                LOGGER.error("A 'version' key is not specified for 'toolbox/{}' setting".format(toolset_name))
                return

            if toolset_version == "devel":
                continue

            pipeline_dir = utils.resolve(config.get_value("pipeline_dir"))

            toolset_dir = os.path.join(pipeline_dir, "toolbox", toolset_name, toolset_version)

            if not os.path.exists(toolset_dir):

                if not config.get_value("is_centralized", False):
                    if not installer.install(toolset_name, toolset_version):
                        LOGGER.error("Unable to install revision '{}' "
                                     "of '{}' toolset".format(toolset_version, toolset_name))
                        return
                else:
                    LOGGER.error("Revision '{}' "
                                 "of '{}' toolset is not installed yet".format(toolset_version, toolset_name))

                    return

            revision_sha256_path = os.path.join(toolset_dir, ".sha256")
            if not os.path.exists(revision_sha256_path):
                LOGGER.error("Revision '{}' of '{}' toolset has missing "
                             "checksum file. Please make sure the "
                             "synchronization is finished.".format(toolset_version, toolset_name))
                return

            with open(revision_sha256_path, "r") as f:
                revision_sha256 = f.read()

            if revision_sha256 != utils.get_directory_hash(toolset_dir):
                LOGGER.error("Unable to load revision '{}' "
                             "of '{}' toolset. Checksum mismatch. Please make sure the "
                             "toolset is installed correctly.".format(toolset_version, toolset_name))
                return

        toolsets_to_load.append((toolset_name, toolset_version, toolset_dir))

    return toolsets_to_load


def load_toolsets(
        app_name,
        app_version=None,
        devel=False):
    """Find and load all toolsets

    Args:
        app_name (str): the name of the app to load modules for (e.g. houdini, maya, ...).

    Kwargs:
        app_version (str): the version of the app to load modules for(2017.5, 16.0.736, ...).
        devel (bool): whether to load development toolsets first.

    Returns:
        True on success, False otherwise.

    """
    LOGGER.info("Loading toolsets for {}-{}".format(app_name, app_version))

    proj_preset_dir = utils.resolve(config.get_value("proj_preset_dir"))

    this_directory = os.path.dirname(os.path.abspath(__file__))

    # load hooks
    hook_search_paths = [
        os.path.join(this_directory, "hooks"),
        os.path.join(proj_preset_dir, "hooks")
    ]

    hooks.load_hooks(hook_search_paths)

    ENV.prepend("PYTHONPATH", os.path.join(proj_preset_dir, "resources", "python"))

    toolsets_to_load = get_available_toolsets(devel)

    if not toolsets_to_load:
        return False

    ENV.putenv("BD_HOOKPATH", os.path.join(proj_preset_dir, "hooks"))

    all_toolset_names = frozenset([name for name, _, _ in toolsets_to_load])

    for toolset_name, toolset_version, toolset_dir in toolsets_to_load:

        LOGGER.info('{} - {} - {}'.format(toolset_name,
                                          toolset_version,
                                          toolset_dir))

        missing_toolsets = _check_dependencies(toolset_name, toolset_dir, all_toolset_names)

        if missing_toolsets:
            LOGGER.warning("Toolset '{}' has missing dependencies: "
                           "{}".format(toolset_name, ', '.join(missing_toolsets)))
            return False

        # execute initializer inside toolset directory
        _execute_bd_init(toolset_dir)

        _load_python_environment(toolset_dir)
        if app_name != "python":
            _load_app_environment(toolset_dir, app_name, app_version)

        hooks_dir = os.path.join(toolset_dir, "hooks")
        if os.path.isdir(hooks_dir):
            ENV.append("BD_HOOKPATH", hooks_dir)

        ENV[toolset_name.upper().replace("-", "_") + "_DIR"] = toolset_dir

    hooks.execute("bd.loader.finalize", ENV).all()

    return True


def list_toolsets(devel=False):
    """
    List all toolsets available for loading.

    Kwargs:
        devel  (bool): whether to load development toolsets first.

    """
    toolsets_to_load = get_available_toolsets(devel)

    if not toolsets_to_load:
        LOGGER.warning("There is no toolsets to list")
        return

    for toolset_name, toolset_version, toolset_dir in toolsets_to_load:

        LOGGER.info('{} - {} - {}'.format(toolset_name,
                                          toolset_version,
                                          toolset_dir))