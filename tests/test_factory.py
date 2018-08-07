import os
import mock
import unittest

import bd.factory
from bd.exceptions import *


class bd_factory_create_TestCase(unittest.TestCase):

    @mock.patch("bd.factory.factory.config")
    def test_config_error(self, mock_config):
        mock_config.get_value.side_effect = Error()
        self.assertRaises(Error, bd.factory.create, "toolset_name")

    @mock.patch("bd.factory.factory.os.path")
    @mock.patch("bd.factory.factory.config")
    def test_if_development_dir_does_not_exist(self, mock_config, mock_path):
        mock_config.get_value.return_value = "some_path"
        mock_path.exists.return_value = False
        self.assertRaises(FilesystemPathNotFoundError, bd.factory.create, "toolset_name")

    @mock.patch("bd.factory.factory.os.path")
    @mock.patch("bd.factory.factory.config")
    def test_if_toolset_dir_exists(self, mock_config, mock_path):
        mock_config.get_value.return_value = "some_path"
        mock_path.exists.side_effect = [True, True]
        self.assertRaises(OverwriteNotPermittedError, bd.factory.create, "toolset_name")

    @mock.patch("bd.factory.factory.utils.cleanup")
    @mock.patch("bd.factory.factory._init_all")
    @mock.patch("bd.factory.factory.os.path")
    @mock.patch("bd.factory.factory.config")
    def test_if_initialization_failed_and_toolset_dir_was_created_and_cleanup_ok(self,
                                                                                 mock_config,
                                                                                 mock_path,
                                                                                 mock_init_all,
                                                                                 mock_cleanup):
        mock_config.get_value.return_value = "some_path"
        mock_path.exists.side_effect = [True, False, True]
        mock_init_all.side_effect = Error()
        mock_cleanup.return_value = True
        self.assertRaises(Error, bd.factory.create, "toolset_name")

    @mock.patch("bd.factory.factory._init_all")
    @mock.patch("bd.factory.factory.os.path")
    @mock.patch("bd.factory.factory.config")
    def test_perfect_flow(self, mock_config, mock_path, mock_init_all):
        mock_config.get_value.return_value = "some_path"
        mock_path.exists.side_effect = [True, False]
        mock_init_all.return_value = None
        self.assertIsNone(bd.factory.create("toolset_name"))

    @mock.patch("bd.factory.factory.utils.cleanup")
    @mock.patch("bd.factory.factory._init_all")
    @mock.patch("bd.factory.factory.os.path")
    @mock.patch("bd.factory.factory.config")
    def test_if_initialization_failed_and_toolset_dir_was_created_and_cleanup_failed(self,
                                                                                     mock_config,
                                                                                     mock_path,
                                                                                     mock_init_all,
                                                                                     mock_cleanup):
        mock_config.get_value.return_value = "some_path"
        mock_path.exists.side_effect = [True, False, True]
        mock_init_all.side_effect = Error()
        mock_cleanup.side_effect = TypeError()
        self.assertRaises(TypeError, bd.factory.create, "toolset_name")


class bd_factory_init_all_TestCase(unittest.TestCase):

    @mock.patch("bd.factory.factory.os")
    def test_makedirs_failed(self, mock_os):
        mock_os.makedirs.side_effect = OSError()
        self.assertRaises(UnableToMakeDirectoryError, bd.factory.factory._init_all, "sdfgsdfgsd")

    @mock.patch("bd.factory.factory.config")
    @mock.patch("bd.factory.factory.os")
    def test_config_invalid_repo_url_format(self, mock_os, mock_config):
        mock_os.makedirs.return_value = None
        mock_config.get_value.return_value = "wrong_repository_url_format"
        self.assertRaises(InvalidRepositoryUrlFormatError,
                          bd.factory.factory._init_all,
                          "toolset_directory_path")

    @mock.patch("bd.factory.factory.git.Repo")
    @mock.patch("bd.factory.factory.os")
    @mock.patch("bd.factory.factory.config")
    def test_cloning_failed(self,
                            mock_config,
                            mock_os,
                            mock_repo):
        mock_os.makedirs.return_value = None
        mock_config.get_value.return_value = "git@github.com:whatever/{name}.git"
        mock_repo.clone_from.side_effect = bd.factory.factory.git.exc.GitError()
        self.assertRaises(UnableToCloneRepositoryError,
                          bd.factory.factory._init_all,
                          "toolset_directory_path")

    @mock.patch("bd.factory.factory.git.Repo")
    @mock.patch("bd.factory.factory.utils.cleanup")
    @mock.patch("bd.factory.factory._init_repository")
    @mock.patch("bd.factory.factory.os")
    @mock.patch("bd.factory.factory.config")
    def test_perfect_flow(self,
                          mock_config,
                          mock_os,
                          mock_init_repository,
                          mock_cleanup,
                          mock_repo):
        mock_os.makedirs.return_value = None
        mock_config.get_value.return_value = "git@github.com:whatever/{name}.git"
        mock_repo.clone_from.return_value = mock.MagicMock()
        mock_cleanup.return_value = None
        mock_init_repository.return_value = None
        self.assertIsNone(bd.factory.factory._init_all("toolset_directory_path"))


class bd_factory_init_repository_TestCase(unittest.TestCase):

    @mock.patch("bd.factory.factory.git.Repo")
    def test_repo_init_error(self, mock_repo):
        mock_repo.init.side_effect = bd.factory.factory.git.exc.GitError()
        mock_repo.return_value.close.return_value = None
        self.assertRaises(RepositoryInitializationError,
                          bd.factory.factory._init_repository,
                          "toolset_directory_path",
                          "git@github.com:whatever/repository.git")

    @mock.patch("bd.factory.factory.git.Repo")
    def test_repo_create_remote_error(self, mock_repo):
        mock_repo.init.return_value = mock.MagicMock()
        mock_repo.init.return_value.create_remote.side_effect = ValueError("asdasd")
        mock_repo.return_value.close.return_value = None
        self.assertRaises(RepositoryInitializationError,
                          bd.factory.factory._init_repository,
                          "toolset_directory_path",
                          "git@github.com:whatever/repository.git")

    def test_invalid_repo_url_format(self):
        self.assertRaises(InvalidRepositoryUrlFormatError,
                          bd.factory.factory._init_repository,
                          "toolset_directory_path",
                          "wrong_repository_url_format")


if __name__ == '__main__':
    unittest.main()