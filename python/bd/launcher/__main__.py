import os
import re
import getpass
from argparse import ArgumentParser

from bd.logger import get_logger
from bd import config
from bd import launcher
from bd.exceptions import *

LOGGER = get_logger(__name__)


def _add_args(parser):
    parser.add_argument("app_name",
                        help="The name of the application to launch",
                        type=str)
    parser.add_argument("-v", "--app-version",
                        help="Application version",
                        type=str)


def main():
    parser = ArgumentParser(prog="bd-launch")

    _add_args(parser)

    args, unknown_args = parser.parse_known_args()

    try:
        config.load()
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)

    sys.exit(launcher.launch(args.app_name,
                             args.app_version,
                             unknown_args))


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())