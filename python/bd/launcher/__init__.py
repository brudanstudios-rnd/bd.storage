import os

from ..logger import get_logger
from .. import config
from .. import loader

LOGGER = get_logger(__name__)


def launch(app_name,
           app_version,
           unknown_args=[]):

    if not loader.load_toolsets(app_name, app_version):
        return 1

    if not app_version or app_version == "default":
        app_infos = config.get_value('/'.join(["launchers", app_name]))
        for app_version, app_launch_data in app_infos.iteritems():
            if app_version == "default":
                app_version = app_launch_data
                break

    command = config.get_value('/'.join(["launchers", app_name, app_version]))

    if not command:
        return 1

    command = ' '.join([command] + unknown_args)

    LOGGER.info("Running '{}'".format(command))

    os.system(command)