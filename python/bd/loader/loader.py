# -*- coding: utf-8 -*-
__all__ = ["load_toolsets", "list_toolsets", "get_available_toolsets"]

import os
import logging

from pathlib2 import Path

from .. import config
from .. import hooks

from .environment import ENV
from .. import utils


LOGGER = logging.getLogger("bd.loader.loader")


def _execute_bd_init(directory):

    init_path = directory / "bd_init.py"

    if not init_path.exists():
        init_path = directory / "bd_init.pyc"

        if not init_path.exists():
            return

    LOGGER.debug("Calling initializer '{}'".format(init_path))

    CWD = directory

    try:
        utils.execute_file(init_path, globals(), locals())
    except Exception:
        LOGGER.exception("Unable to execute initializer due to the error:")


def _load_app_environment(toolset_dir, app_name, app_version):

    # find a directory inside the toolset for the specified app
    # e.g. houdini, maya, ...
    app_dir = toolset_dir / app_name
    if not app_dir or not app_dir.is_dir():
        return

    # every app directory stores a version of the
    # matching application version
    # e.g. 2018, 16.0.736, ...
    app_dir_versions = sorted(app_dir.iterdir(), reverse=True)

    if not app_dir_versions:
        LOGGER.error("Unable to find any versioned "
                     "sub-directory in '{}'".format(app_dir))
        return

    # execute initializer inside app directory
    _execute_bd_init(app_dir)

    app_version_dir = None

    if app_version:
        app_version_dir = app_dir / app_version

    if not app_version_dir or not app_version_dir.exists():
        latest_app_version = next((version_dir.name
                                    for version_dir in app_dir_versions
                                    if version_dir.is_dir()))

        app_version_dir = app_dir / latest_app_version

    hooks.execute("bd.loader.initialize.{}".format(app_name), app_version_dir, ENV).all()

    _execute_bd_init(app_version_dir)


def _load_python_environment(toolset_dir):

    # find a 'python' directory inside the toolset
    python_dir = toolset_dir / "python"
    if not python_dir.is_dir():
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
            devel_toolset_dir = Path(config.get_value("development_dir")) / "toolbox" / toolset_name
            if devel_toolset_dir.exists():
                toolset_dir = devel_toolset_dir

        if not toolset_dir:

            toolset_version = toolset_config.get("version")
            if not toolset_version:
                LOGGER.error("A 'version' key is not specified for 'toolbox/{}' setting".format(toolset_name))
                return

            if toolset_version == "devel":
                continue

            toolset_dir = Path(config.get_value("pipeline_dir")) / "toolbox" / toolset_name / toolset_version
            if not toolset_dir.exists():
                LOGGER.error("Unable to find revision '{}' "
                             "of '{}' toolset".format(toolset_version, toolset_name))
                return

            revision_md5_path = toolset_dir / ".md5"
            if not revision_md5_path.exists():
                LOGGER.error("Revision '{}' of '{}' toolset has missing "
                             "checksum file. Please make sure the "
                             "synchronization is finished.".format(toolset_version, toolset_name))
                return

            revision_md5 = revision_md5_path.read_text()

            if revision_md5 != utils.get_directory_md5(toolset_dir):
                LOGGER.error("Unable to load revision '{}' "
                             "of '{}' toolset. Checksum mismatch. Please make sure the "
                             "synchronization is finished.".format(toolset_version, toolset_name))
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
    LOGGER.info("app_name: {0} | app_version: {1}".format(app_name,
                                                          app_version))

    proj_config_dir = Path(config.get_value("proj_config_dir"))

    if not proj_config_dir.exists():
        LOGGER.error("Project configuration directory"
                     " '{}' doesn't exist".format(proj_config_dir))
        return False

    # load hooks
    hook_search_paths = [
        Path(os.path.dirname(os.path.abspath(__file__))) / "hooks",
        proj_config_dir / "hooks"
    ]

    hooks.load_hooks(hook_search_paths)

    toolsets_to_load = get_available_toolsets(devel)

    if not toolsets_to_load:
        return False

    LOGGER.info("Loading toolsets:")

    ENV.putenv("BD_HOOKPATH", proj_config_dir / "hooks")

    all_toolset_names = frozenset([name for name, _, _ in toolsets_to_load])

    for toolset_name, toolset_version, toolset_dir in toolsets_to_load:

        LOGGER.info('{:20} | {:10} | {}'.format(toolset_name,
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

        hooks_dir = toolset_dir / "hooks"
        if hooks_dir.is_dir():
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
    proj_config_dir = Path(config.get_value("proj_config_dir"))
    if not proj_config_dir.exists():
        LOGGER.error("Project configuration directory"
                     " '{}' doesn't exist".format(proj_config_dir))
        return

    toolsets_to_load = get_available_toolsets(devel)

    if not toolsets_to_load:
        LOGGER.warning("There is no toolsets to list")
        return

    for toolset_name, toolset_version, toolset_dir in toolsets_to_load:

        print '{:20} | {:10} | {}'.format(toolset_name, toolset_version, toolset_dir)