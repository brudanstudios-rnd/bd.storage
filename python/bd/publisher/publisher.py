import logging

import pathlib2
import git

from .. import config

LOGGER = logging.getLogger("bd.publisher.publisher")


def publish(name, release):
    toolset_dir = pathlib2.Path(config.get_value("development_dir")) / "toolbox" / name
    if not toolset_dir.exists():
        LOGGER.error("Directory '{}' doesn't exist".format(toolset_dir))
        return False

    str_toolset_dir = str(toolset_dir.resolve())

    # get a local repository from the current directory
    try:
        repo = git.Repo(str_toolset_dir)
    except git.exc.InvalidGitRepositoryError:
        LOGGER.error("Unable to find any Git repository in '{}'".format(str_toolset_dir))
        return False

    commit = repo.head.commit

    commit_msg = commit.message.strip()

    tag = repo.create_tag(release, message=commit_msg)
    repo.remotes.origin.push(tag)

    return True
