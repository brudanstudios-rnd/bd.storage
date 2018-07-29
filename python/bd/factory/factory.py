# -*- coding: utf-8 -*-
__all__ = ["create"]

import logging

import git
from pathlib2 import Path

from .. import config
from .. exceptions import *
from .. import utils

LOGGER = logging.getLogger("bd.factory.factory")


def _init_repository(toolset_dir, repo_url_format):

    repo_url = repo_url_format.format(name=toolset_dir.name)

    repo = None

    try:
        LOGGER.info("Initializing repository ...")

        repo = git.Repo.init(str(toolset_dir.resolve()))
        repo.index.add(repo.untracked_files)
        repo.index.commit("initial commit")

        LOGGER.info("done.")

        LOGGER.info("Connecting remote repository '{}' ...".format(repo_url))

        origin = repo.create_remote("origin", url=repo_url)
        origin.push(refspec='master:master')

        LOGGER.info("done.")

    except git.exc.GitCommandError, e:
        LOGGER.error(e)
        return False

    finally:
        try:
            repo.close()
        except:
            pass

    return True


def _init_all(toolset_dir):

    toolset_dir.mkdir(parents=True)

    repo_url_format = config.get_value("git_repo_url_format")

    repo_url = repo_url_format.format(name="bd-toolset-template")

    try:
        LOGGER.info("Cloning '{}' repository ...".format(repo_url))
        git.Repo.clone_from(repo_url, str(toolset_dir)).close()
        LOGGER.info("done.")
    except git.exc.GitCommandError, e:
        LOGGER.error(e.stderr.strip())
        return False

    utils.cleanup(toolset_dir, [".git"])

    return _init_repository(toolset_dir, repo_url_format)


def create(name):
    try:
        development_dir = Path(config.get_value("development_dir"))
        if not development_dir.exists():
            raise BDFilesystemPathNotFound(str(development_dir))

        toolset_dir = development_dir / "toolbox" / name
        if toolset_dir.exists():
            raise BDUnableToOverwrite(str(toolset_dir))

        if not _init_all(toolset_dir):
            utils.cleanup(toolset_dir)
            return False

    except BDException as e:
        LOGGER.error(e)

    else:
        return True
