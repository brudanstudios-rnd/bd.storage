# -*- coding: utf-8 -*-
__all__ = ["create"]
import os

import git

from ..logger import get_logger
from .. import config
from .. exceptions import *
from .. import utils

LOGGER = get_logger(__name__)

join = os.path.join
exists = os.path.exists


def _init_repository(toolset_dir, github_account):

    repo_name = os.path.basename(toolset_dir)

    repo_url = "git@github.com:{}/{}.git".format(github_account, repo_name)

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
        os.makedirs(toolset_dir)
    except OSError as e:
        raise UnableToMakeDirectoryError(details={"dirname": toolset_dir,
                                                  "exc_msg": str(e)})

    github_account = os.environ["BD_GITHUB_ACCOUNT"]

    repo_url = "git@github.com:{}/bd-toolset-template.git".format(github_account)

    try:
        LOGGER.info("Cloning '{}' repository ...".format(repo_url))
        git.Repo.clone_from(repo_url, toolset_dir).close()
        LOGGER.info("done.")
    except git.exc.GitError, e:
        raise UnableToCloneRepositoryError(details={"repo_url": repo_url,
                                                    "dirname": toolset_dir,
                                                    "exc_msg": str(e)})

    utils.cleanup(toolset_dir, [".git"])

    _init_repository(toolset_dir, github_account)


def create(name):

    development_dir = utils.resolve(os.environ["BD_DEVEL_DIR"])
    if not exists(development_dir):
        os.makedirs(development_dir, exist_ok=True)

    toolset_dir = join(development_dir, name)
    if exists(toolset_dir):
        raise OverwriteNotPermittedError(details={"path": toolset_dir})

    try:
        _init_all(toolset_dir)
    except Error:
        if exists(toolset_dir):
            utils.cleanup(toolset_dir)
        raise
