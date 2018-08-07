import os
import re
import logging
import getpass
from argparse import ArgumentParser

import bd.config as config
import bd.loader as loader
from bd.exceptions import *

LOGGER = logging.getLogger("bd.launcher")


def _add_args(parser):
    parser.add_argument("app_name",
                        help="The name of the application to launch",
                        type=str)
    parser.add_argument("-u", "--user", type=str,
                        help="Run as a specific user")
    parser.add_argument("-v", "--app-version",
                        help="Application version",
                        type=str,
                        default="default")
    parser.add_argument("--devel",
                        help="Switch to a development mode",
                        action="store_true")


def _launch(app_name,
            app_version,
            devel=False,
            unknown_args=[]):

    if not loader.load_toolsets(app_name, app_version, devel):
        sys.exit(1)

    command = config.get_value('/'.join(["paths", app_name, app_version]))

    if not command:
        sys.exit(1)

    command = ' '.join([command] + unknown_args)
    LOGGER.debug("Running '{}'".format(command))

    return os.system(command)


def main():
    parser = ArgumentParser(prog="bd-launch")

    _add_args(parser)

    args, unknown_args = parser.parse_known_args()

    logging.basicConfig(level=logging.INFO)

    user = os.getenv("BD_USER", getpass.getuser())
    os.environ["BD_USER"] = args.user if args.user else user

    if not os.getenv("BD_CONFIG_NAME"):
        LOGGER.error("Please specify a project configuration name.")
        sys.exit(1)

    try:
        config.load()
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)

    sys.exit(_launch(args.app_name,
                     args.app_version,
                     args.devel,
                     unknown_args))


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())