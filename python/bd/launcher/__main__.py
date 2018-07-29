import os
import sys
import re
import logging
import tempfile
import cPickle
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
    parser.add_argument("-c", "--config-name", type=str,
                        help="Project configuration name",
                        required=True)
    parser.add_argument("-v", "--app-version",
                        help="Application version",
                        type=str,
                        default="default")
    parser.add_argument("--command",
                        help="Command to execute",
                        type=str)
    parser.add_argument("--devel",
                        help="Switch to a development mode",
                        action="store_true")


def _launch(app_name,
            app_version,
            command=None,
            devel=False):

    if not loader.load_toolsets(app_name, app_version, devel):
        sys.exit(1)

    if not command:
        command = config.get_value('/'.join(["dcc_paths", app_name, app_version]))

        if not command:
            sys.exit(1)

    LOGGER.debug("Running '{}'".format(command))

    return os.system(command)


def main():
    parser = ArgumentParser(prog="bd-launch")

    _add_args(parser)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    user = os.getenv("BD_USER", getpass.getuser())
    os.environ["BD_USER"] = args.user if args.user else user

    config_name = os.getenv("BD_CONFIG_NAME", "undefined")
    os.environ["BD_CONFIG_NAME"] = args.config_name if args.config_name else config_name

    try:
        config.load()
    except BDException as e:
        LOGGER.error(e)
        sys.exit(1)

    sys.exit(_launch(args.app_name,
                     args.app_version,
                     args.command,
                     args.devel))


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())