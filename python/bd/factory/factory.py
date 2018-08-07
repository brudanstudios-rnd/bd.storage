# -*- coding: utf-8 -*-
__all__ = ["create"]
import os
import re
import logging

import git

from .. import config
from .. exceptions import *
from .. import utils

LOGGER = logging.getLogger("bd.factory.factory")

GIT_REPO_URL_REGEX = re.compile(r"((git|ssh|http(s)?)|(git@[\w\.]+))(:(//)?)([\w\.@\:/\-~]+)(\.git)(/)?")


def _init_repository(toolset_dir, repo_url_format):

    repo_name = os.path.basename(toolset_dir)

    repo_url = repo_url_format.format(name=repo_name)
    if not GIT_REPO_URL_REGEX.match(repo_url):
        raise InvalidRepositoryUrlFormatError(repo_url)

    repo = None

    try:
        LOGGER.info("Initializing repository ...")

        repo = git.Repo.init(toolset_dir)

        LOGGER.info("done.")

        LOGGER.info("Connecting remote repository '{}' ...".format(repo_url))

        repo.create_remote("origin", url=repo_url)

        LOGGER.info("done.")

    except (git.exc.GitError, ValueError), e:
        raise RepositoryInitializationError(details={"repo_url": repo_url,
                                                     "dirname": toolset_dir,
                                                     "exc_msg": str(e)})

    finally:
        try:
            if repo:
                repo.close()
        except git.exc.GitError as e:
            LOGGER.warning("Unable to close '{}' repository. {}".format(repo_name, e))


def _init_all(toolset_dir):
    try:
        os.makedirs(toolset_dir, exist_ok=True)
    except OSError as e:
        raise UnableToMakeDirectoryError(details={"dirname": toolset_dir,
                                                  "exc_msg": str(e)})

    repo_url_format = config.get_value("git_repo_url_format")

    repo_url = repo_url_format.format(name="bd-toolset-template")
    if not GIT_REPO_URL_REGEX.match(repo_url):
        raise InvalidRepositoryUrlFormatError(details={"repo_url": repo_url})

    try:
        LOGGER.info("Cloning '{}' repository ...".format(repo_url))
        git.Repo.clone_from(repo_url, toolset_dir).close()
        LOGGER.info("done.")
    except git.exc.GitError, e:
        raise UnableToCloneRepositoryError(details={"repo_url": repo_url,
                                                    "dirname": toolset_dir,
                                                    "exc_msg": str(e)})

    utils.cleanup(toolset_dir, [".git"])

    _init_repository(toolset_dir, repo_url_format)


def create(name):

    development_dir = config.get_value("development_dir")
    if not os.path.exists(development_dir):
        raise FilesystemPathNotFoundError(details={"path": development_dir})

    toolset_dir = os.path.join(os.path.abspath(development_dir), "toolbox", name)
    if os.path.exists(toolset_dir):
        raise OverwriteNotPermittedError(details={"path": toolset_dir})

    try:
        _init_all(toolset_dir)
    except Error:
        if os.path.exists(toolset_dir):
            utils.cleanup(toolset_dir)
        raise
