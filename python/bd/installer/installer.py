# -*- coding: utf-8 -*-
__all__ = ["install"]

import os
import logging
import tempfile
import shutil
import fnmatch
import compileall

import git
from pathlib2 import Path

from .. import config
from .. import utils

LOGGER = logging.getLogger("bd.installer.installer")


class TempDirContext(object):
    
    def __init__(self):
        self._tmp_dir = Path(tempfile.mkdtemp())

    @property
    def dirname(self):
        return self._tmp_dir

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        utils.cleanup(self._tmp_dir)


def _compile(root_dir, cmpl_ignored=[]):

    # delete .py files
    for py_filepath in root_dir.rglob("*.py"):
        utils.minify(str(py_filepath))

        is_ignored = False
        if cmpl_ignored:
            is_ignored = any(map(lambda x: fnmatch.fnmatch(py_filepath.name, x), cmpl_ignored))

        if is_ignored:
            continue

        compileall.compile_file(str(py_filepath), force=True)
        py_filepath.unlink()


def install(name, release=None, devel=False):
    """
    Install toolset revision.

    Clones a tagged commit from the central repository into the destination
    directory with a structure like this:
        If 'devel':
            {pipeline_dir}/devel/{user}/toolbox/{name}
        else:
            {pipeline_dir}/configs/{project}/toolbox/{name}/{release}

    If installed for the development purpose there is no point to have
    the name of the branch as an intermediate directory.

    Args:
        name (str): a toolset name to install.
    Kwargs:
        release (str): a name of the release to clone.

        devel (bool): if True the toolset will be installed for the development
            purpose. The difference is that the development
            installation has git specific files and folders, e.g ".git" and ".gitignore".
            Also non-devel repository is compiled.

    Returns:
        str. A path to the installed toolset on success, None otherwise.

    """
    if devel:
        root_dir = Path(config.get_value("development_dir", "none"))
    else:
        root_dir = Path(config.get_value("pipeline_dir", "none"))

        if not root_dir.exists():
            LOGGER.error("Project configuration directory"
                         " '{}' doesn't exist".format(root_dir))
            return

    toolbox_dir = root_dir / "toolbox"

    if not toolbox_dir.exists():
        try:
            LOGGER.info("Creating '{}' directory ...".format(toolbox_dir))

            toolbox_dir.mkdir(parents=True, exist_ok=True)

            LOGGER.info("done.")
        except Exception as e:
            LOGGER.error("Unable to create directory: '{}' \n{}".format(toolbox_dir, e))
            return

    toolset_dir = toolbox_dir / name

    if not devel and release and (toolset_dir / release).exists():
        LOGGER.info("Toolset revision '{}' is already installed".format(release))
        return

    with TempDirContext() as tdc:

        tmp_dir = tdc.dirname

        repo_url_format = config.get_value("git_repo_url_format")

        if not repo_url_format:
            LOGGER.error("Unable to find config setting:"
                         " 'git_repo_url_format'")
            return

        repo_url = repo_url_format.format(name=name)

        try:
            LOGGER.info("Cloning '{}' repository ...".format(repo_url))

            repo = git.Repo.clone_from(repo_url, str(tmp_dir))

            LOGGER.info("done.")
        except git.exc.GitCommandError, e:
            LOGGER.error(e.stderr.strip())
            return

        if not devel:
            # get a TagReference object from the 'release' name
            # or if there was no 'release' name provided use
            # the latest existing release
            if release:
                ref = repo.tag("refs/tags/{}".format(release))
                if not ref.is_valid():
                    LOGGER.error("Release '{}' is invalid.".format(ref.name))
                    return
            else:
                sorted_tags = sorted(repo.tags,
                                     key=lambda tag_ref: tag_ref.commit.committed_date)

                if not sorted_tags:
                    LOGGER.error("Could not find any release to clone.")
                    return

                ref = sorted_tags[-1]

            # git checkout to 'ref' and hard reset a working tree
            repo.head.reset(ref, index=True, working_tree=True)

            LOGGER.info("Current revision: '{}'.".format(ref.name))

            toolset_dir = toolset_dir / ref.name

            compile_ignored = []

            toolset_metadata = utils.get_toolset_metadata(tmp_dir)
            if toolset_metadata:
                compile_ignored = toolset_metadata.get("keep_source", [])

            _compile(tmp_dir, compile_ignored)
        else:
            if release:
                ref = repo.tag("refs/tags/{}".format(release))
                if not ref.is_valid():
                    LOGGER.error("Tag '{}' is invalid.".format(ref.name))
                    return

                # git checkout to 'ref' and hard reset a working tree
                repo.head.reset(ref, index=True, working_tree=True)

        repo.close()

        # { create a parent directory tree for the installation directory
        parent_dir = toolset_dir.parent
        if not parent_dir.exists():
            try:
                LOGGER.info("Creating '{}' directory ...".format(parent_dir))

                parent_dir.mkdir(parents=True, exist_ok=True)

                LOGGER.info("done.")
            except Exception as e:
                LOGGER.error("Unable to create directory tree: '{}' \n{}".format(parent_dir, e))
                return
        # }

        def get_ignored_names(src, names):
            """Filter function to use in shutil.copytree"""
            return [name for name in names if name in [".git", ".gitignore"]]

        # copy all the nested files and folders from the repository
        # to the installation directory skipping those returned by
        # 'get_ignored_names' function
        try:
            LOGGER.info("Moving files into '{}' ...".format(toolset_dir))

            shutil.copytree(str(tmp_dir),
                            str(toolset_dir),
                            ignore=(get_ignored_names if not devel else None))

            LOGGER.info("done.")
        except Exception as e:
            LOGGER.error("Unable to copy files into "
                         "directory: '{}' \n{}".format(toolset_dir, e))
            return

        if not devel:
            try:
                LOGGER.info("Calculating checksum ...")

                checksum = utils.get_directory_md5(toolset_dir)
                (toolset_dir / ".md5").write_text(unicode(checksum))

                LOGGER.info("done.")
            except Exception as e:
                LOGGER.exception("Unable calculate checksum for the "
                                 "directory '{}'".format(toolset_dir))
                return

    return toolset_dir
