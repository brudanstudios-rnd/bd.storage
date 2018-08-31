import os
import sys
import git
import logging
import tempfile

import shutil
from .. import utils
from .. import config

LOGGER = logging.getLogger(__name__)


def publish():
    repo_path = os.getcwd()

    # get a local repository from the current directory
    try:
        repo = git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        LOGGER.error("Unable to find any Git repository in '{}'".format(repo_path))
        return False

    remotes = repo.remotes
    if not remotes:
        LOGGER.error("Unable to find any remote repository "
                     "associated with the directory '{}'".format(repo_path))
        return False

    repo_url = remotes[0].url

    repo_name = repo_url.rsplit('/', 1)[-1].replace('.git', '')

    if repo.is_dirty(untracked_files=True):
        LOGGER.error("There are uncommitted changes in the current repository")
        return False

    if not repo.tags:
        LOGGER.error("Please Tag your repository before publishing it")
        return False

    latest_tag = None

    committed_date = 0
    for tag in repo.tags:
        if committed_date < tag.commit.committed_date:
            committed_date = tag.commit.committed_date
            latest_tag = tag

    tree = repo.heads.master.commit.tree

    accepted = map(lambda x: x.path, tree.trees + tree.blobs)

    setup_path = os.path.join(repo_path, "setup.py")
    if os.path.exists(setup_path):
        accepted.append(setup_path)

    tmp_dir = tempfile.mktemp()

    try:
        shutil.copytree(repo_path, tmp_dir,
                        ignore=lambda src, names: [] if src != repo_path else
                        set(names).difference(accepted))

        utils.compile(tmp_dir)

        repo = git.Repo.init(tmp_dir)

        repo_url = "git@github.com:{}/{}.git".format(
            config.get_value("github_account"),
            config.get_value("github_deploy_repo")
        )

        origin = repo.create_remote("origin", url=repo_url)

        repo.git.add('--all')
        repo.index.commit(latest_tag.name)

        artifact_name = '{}/{}'.format(repo_name, latest_tag.name)

        repo.create_tag(artifact_name)
        repo.git.push("origin", artifact_name)
    except:
        shutil.rmtree(tmp_dir)
        raise

    return True