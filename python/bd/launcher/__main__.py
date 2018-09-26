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
    parser.add_argument("-u", "--user", type=str,
                        help="Run as a specific user")
    parser.add_argument("-v", "--app-version",
                        help="Application version",
                        type=str)
    parser.add_argument("--devel",
                        help="Switch to a development mode",
                        action="store_true")


def main():
    parser = ArgumentParser(prog="bd-launch")

    _add_args(parser)

    args, unknown_args = parser.parse_known_args()

    user = os.getenv("BD_USER", getpass.getuser())
    os.environ["BD_USER"] = args.user if args.user else user

    if not os.getenv("BD_PRESET"):
        LOGGER.error("Please specify a project preset name.")
        sys.exit(1)

    try:
        config.load()
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)

    sys.exit(launcher.launch(args.app_name,
                             args.app_version,
                             args.devel,
                             unknown_args))


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())