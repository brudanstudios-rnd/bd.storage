# -*- coding: utf-8 -*-
__all__ = ["install"]

import os

from bd_installer import install_artifact

from ..logger import get_logger
from .. import config
from .. import utils

join = os.path.join
exists = os.path.exists

LOGGER = get_logger(__name__)


def install(name, version):
    """
    Install a specific version of the pre-built toolset.

    Downloads a tagged artifact from the central repository into the destination
    directory with a structure like this:

    {pipeline_dir}/toolbox/{name}/{version}

    Args:
        name (str): a toolset name to install.
        version (str): the version to clone (usually in the format vx.x.x).

    Returns:
        True on success, False otherwise.

    """

    toolbox_dir = utils.resolve(config.get_value("toolbox_dir"))

    return install_artifact(
        name,
        version,
        toolbox_dir,
        config.get_value("github_deploy_repo")
    )