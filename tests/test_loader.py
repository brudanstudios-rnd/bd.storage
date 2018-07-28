import os
import subprocess
import nose


def test_not_activated_pipeline():
    pipeline_dir = os.getenv("BD_PIPELINE_DIR")
    if pipeline_dir:
        os.environ.pop("BD_PIPELINE_DIR")

    nose.tools.assert_equal(subprocess.call(["python", "-m", "bd.loader", "list"]), 1)

    if pipeline_dir:
        os.environ["BD_PIPELINE_DIR"] = pipeline_dir


def test_not_defined_configuration_name():
    nose.tools.assert_equal(subprocess.call(["python", "-m", "bd.loader", "list"]), 1)


def test_not_defined_user():
    subprocess.check_output(["python", "-m", "bd.loader", "-c", "default", "list"])