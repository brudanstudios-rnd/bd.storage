# -*- coding: utf-8 -*-
__all__ = ["install"]

import os
import logging
import tempfile
import zipfile
import itertools

import requests

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
    LOGGER.info("Installing version '{}' of toolset '{}'".format(version, name))

    toolbox_dir = utils.resolve(config.get_value("toolbox_dir"))

    toolset_dir = join(toolbox_dir, name)

    if not exists(toolset_dir):
        try:
            LOGGER.info("Creating '{}' directory ...".format(toolset_dir))

            os.makedirs(toolset_dir)

            LOGGER.info("done.")
        except Exception as e:
            LOGGER.error("Unable to create directory: '{}' \n{}".format(toolset_dir, e))
            return

    if exists(join(toolset_dir, version)):
        LOGGER.info("Version '{}' of '{}' toolset is already installed".format(version, name))
        return

    github_account = config.get_value("github_account")
    github_deploy_repo = config.get_value("github_deploy_repo")

    archive_url = "https://github.com/{account}/{deploy_repo}/archive/{name}/{version}.zip".format(
        account=github_account,
        deploy_repo=github_deploy_repo,
        name=name,
        version=version
    )

    try:
        response = requests.get(archive_url)
        response.raise_for_status()

    except requests.exceptions.HTTPError as err:
        LOGGER.error(err)
        return

    except requests.exceptions.RequestException as err:
        LOGGER.error("Connection Error: {}".format(err))
        return

    tmp_path = tempfile.mktemp()

    with open(tmp_path, "wb") as f:
        f.write(response.content)

    try:
        with zipfile.ZipFile(tmp_path, "r") as zip_ref:

            zipinfos = []
            for member_name, zipinfo in itertools.izip(zip_ref.namelist(), zip_ref.infolist()):
                zipinfo.filename = '/'.join([version, member_name.split('/', 1)[-1]])
                zipinfos.append(zipinfo)

            zip_ref.extractall(toolset_dir, zipinfos)
    except:
        os.remove(tmp_path)
        raise

    version_dir = join(toolset_dir, version)

    try:
        LOGGER.info("Calculating checksum ...")

        checksum = utils.get_directory_hash(version_dir)
        with open(join(version_dir, ".sha256"), "w") as f:
            f.write(unicode(checksum))

        LOGGER.info("done.")
    except Exception as e:
        LOGGER.exception("Unable to calculate the checksum for the "
                         "directory '{}'".format(version_dir))
        return

    return toolset_dir
