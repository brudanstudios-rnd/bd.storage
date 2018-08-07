import os
import mock
import unittest
import cPickle
import bd.config
from bd.exceptions import *


class bd_config_load_TestCase(unittest.TestCase):

    def test_already_pickled_config(self):
        with mock.patch.dict("os.environ"):

            # incorrect serialization
            os.environ["BD_CONFIG_DATA"] = "ScSvvavas"

            self.assertRaises(Error, bd.config.load)

            config_data = {"project": "TEST"}

            # correct serialization
            serialized_config_data = cPickle.dumps(config_data, 2).encode("base64", "strict")
            os.environ["BD_CONFIG_DATA"] = serialized_config_data

            self.assertDictEqual(bd.config.load(), config_data)

        bd.config._config = None

    @mock.patch("bd.config.Loader.load")
    def test_if_config_was_not_serialized(self, mock_load):
        with mock.patch.dict("os.environ"):

            os.environ.pop("BD_CONFIG_DATA", None)

            # if bd.config.loader.Loader.load() raises error
            mock_load.side_effect = Error()
            self.assertRaises(Error, bd.config.load)

            config_data = {"project": "TEST"}

            mock_load.side_effect = None
            mock_load.return_value = config_data

            self.assertDictEqual(bd.config.load(), config_data)

            self.assertIn("BD_OS", os.environ)
            self.assertIn("BD_CONFIG_DATA", os.environ)
            self.assertIn("BD_PROJECT", os.environ)
            self.assertEqual(os.environ["BD_PROJECT"], "TEST")
            self.assertEqual(os.environ["BD_CONFIG_DATA"], cPickle.dumps(config_data, 2).encode("base64", "strict"))

        bd.config._config = None


class bd_config_get_value_TestCase(unittest.TestCase):

    @mock.patch("bd.config.load")
    def test_no_keys(self, mock_load):
        mock_load.return_value = {}
        self.assertIsNone(bd.config.get_value("somekey"))
        self.assertEqual(bd.config.get_value("somekey", "DEFAULT"), "DEFAULT")

    @mock.patch("bd.config.load")
    def test_different_types_of_keys(self, mock_load):
        mock_load.return_value = {
            "a": {
                "b": {
                    "c": 10
                }
            }
        }
        self.assertEqual(bd.config.get_value("a/b/c///"), 10)
        self.assertIsNone(bd.config.get_value("a/c/d"))
        self.assertEqual(bd.config.get_value("a/c/d", "DEFAULT"), "DEFAULT")

        self.assertIsNone(bd.config.get_value("a/b/c/d"))
        self.assertEqual(bd.config.get_value("a/b/c/d", "DEFAULT"), "DEFAULT")

        mock_load.return_value = {
            "a": {
                "b": {
                    "win": 10,
                    "lin": 11,
                    "mac": 12
                }
            }
        }

        self.assertEqual(bd.config.get_value("a/b"), mock_load.return_value["a"]["b"][bd.config.CURRENT_PLATFORM])

    @mock.patch("bd.config.load")
    def test_exceptions(self, mock_load):
        mock_load.side_effect = Error()
        self.assertRaises(Error, bd.config.get_value, "a/b/c")


class bd_config_loader_TestCase(unittest.TestCase):

    def test_not_activated_pipeline(self):
        with mock.patch.dict("os.environ"):

            os.environ.pop("BD_PIPELINE_DIR", None)

            self.assertRaises(PipelineNotActivatedError, bd.config.loader.Loader.load)

    @mock.patch("bd.config.loader.os.path")
    def test_not_existing_core_config(self, mock_path):
        with mock.patch.dict("os.environ"):

            os.environ["BD_PIPELINE_DIR"] = "/Volumes/asset/pipeline"

            mock_path.exists.return_value = False

            self.assertRaises(FilesystemPathNotFoundError, bd.config.loader.Loader.load)

    @mock.patch("bd.config.loader.os.path")
    @mock.patch("bd.config.loader.metayaml.read")
    def test_not_existing_core_config(self, mock_metayaml_read, mock_path):
        with mock.patch.dict("os.environ"):

            os.environ["BD_PIPELINE_DIR"] = "/Volumes/asset/pipeline"

            mock_path.exists.return_value = True
            mock_metayaml_read.side_effect = Exception()

            self.assertRaises(FailedConfigParsingError, bd.config.loader.Loader.load)

    @mock.patch("bd.config.loader.os.path")
    @mock.patch("bd.config.loader.metayaml.read")
    def test_not_defined_config_key(self, mock_metayaml_read, mock_path):
        with mock.patch.dict("os.environ"):

            os.environ["BD_PIPELINE_DIR"] = "/Volumes/asset/pipeline"

            mock_path.exists.return_value = True
            mock_metayaml_read.return_value = {}

            self.assertRaises(MandatoryKeyNotFoundError, bd.config.loader.Loader.load)

    @mock.patch("bd.config.loader.os.path")
    @mock.patch("bd.config.loader.metayaml.read")
    def test_invalid_core_config_key_type(self, mock_metayaml_read, mock_path):
        with mock.patch.dict("os.environ"):

            os.environ["BD_PIPELINE_DIR"] = "/Volumes/asset/pipeline"

            config_dict = {
                "pipeline_dir": None,
                "configs_dir": "",
                "development_dir": "",
                "proj_config_dir": "",
                "user_config_dir": "",
                "git_repo_url_format": ""
            }

            mock_metayaml_read.return_value = config_dict
            self.assertRaises(ConfigValueTypeError, bd.config.loader.Loader.load)

    @mock.patch("bd.config.loader.os.path")
    @mock.patch("bd.config.loader.metayaml.read")
    def test_not_defined_BD_CONFIG_NAME_environment_variable(self, mock_metayaml_read, mock_path):
        with mock.patch.dict("os.environ"):

            os.environ["BD_PIPELINE_DIR"] = "/Volumes/asset/pipeline"

            config_dict = {
                "pipeline_dir": "",
                "configs_dir": "",
                "development_dir": "",
                "proj_config_dir": "",
                "user_config_dir": "",
                "git_repo_url_format": ""
            }

            mock_metayaml_read.return_value = config_dict

            mock_path.exists.return_value = True
            self.assertDictEqual(bd.config.loader.Loader.load(), config_dict)

    @mock.patch("bd.config.loader.os.walk")
    @mock.patch("bd.config.loader.os.path")
    @mock.patch("bd.config.loader.metayaml.read")
    def test_defined_BD_CONFIG_NAME_environment_variable(self, mock_metayaml_read, mock_path, mock_walk):
        with mock.patch.dict("os.environ"):

            os.environ["BD_CONFIG_NAME"] = "default"
            os.environ["BD_PIPELINE_DIR"] = "/Volumes/asset/pipeline"

            config_dict = {
                "pipeline_dir": "",
                "configs_dir": "",
                "development_dir": "",
                "proj_config_dir": "",
                "user_config_dir": "",
                "git_repo_url_format": ""
            }

            mock_metayaml_read.return_value = config_dict

            # project configuration doesn't exist
            mock_path.exists.side_effect = [True, False]
            self.assertRaises(ProjectConfigurationNotFoundError, bd.config.loader.Loader.load)

            # 'config' directory not found inside project configuration directory
            mock_path.exists.side_effect = [True, True, False]
            self.assertRaises(FilesystemPathNotFoundError, bd.config.loader.Loader.load)

            # not project configuration files found
            mock_path.exists.side_effect = [True, True, True, True]
            mock_walk.return_value = [
                ("", "", ["a.py", "b.py"])
            ]
            self.assertRaises(ProjectConfigFilesNotFound, bd.config.loader.Loader.load)

            # configuration file could not be read
            mock_metayaml_read.side_effect = [config_dict, Exception()]
            mock_path.exists.side_effect = [True, True, True, True]
            mock_walk.return_value = [
                ("", "", ["a.yml", "b.yml"])
            ]
            self.assertRaises(FailedConfigParsingError, bd.config.loader.Loader.load)

            # 'project' key is not defined
            config_dict_proj = {"proj_key": "proj_value"}
            mock_metayaml_read.side_effect = [config_dict, config_dict_proj]
            mock_path.exists.side_effect = [True, True, True, True]
            mock_walk.return_value = [
                ("", "", ["a.yml", "b.yml"])
            ]
            self.assertRaises(MandatoryKeyNotFoundError, bd.config.loader.Loader.load)

            # perfect flow
            config_dict_proj = {"proj_key": "proj_value", "project": "TEST"}
            mock_metayaml_read.side_effect = [config_dict, config_dict_proj]
            mock_path.exists.side_effect = [True, True, True, True]
            mock_walk.return_value = [
                ("", "", ["a.yml", "b.yml"])
            ]
            result = config_dict.copy()
            result.update(config_dict_proj)
            self.assertDictEqual(bd.config.loader.Loader.load(), result)

if __name__ == '__main__':
    unittest.main()