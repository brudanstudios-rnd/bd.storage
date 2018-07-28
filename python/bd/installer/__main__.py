# -*- coding: utf-8 -*-
import os
import re
import sys
from argparse import ArgumentParser
import logging
import getpass

from bd.exceptions import *

LOGGER = logging.getLogger("bd.installer")

try:
    import git
except Exception as e:
    LOGGER.error("Unable to find 'git' command. {}".format(str(e)))
    sys.exit(1)


def _add_args_install(subparsers):
    parser = subparsers.add_parser("install",
                                   help="Install toolset")
    parser.add_argument("name",
                        help="The name of toolset to install",
                        type=str)
    parser.add_argument("-r", "--release",
                        help="Repository release(tag) name to clone",
                        type=str)
    parser.add_argument("--devel",
                        help="Switch to a development mode",
                        action="store_true")
    parser.set_defaults(which="install")


def _add_args(parser):

    subparsers = parser.add_subparsers()

    _add_args_install(subparsers)


def _install(name, release, devel):
    from bd.installer import install
    install(name, release, devel)


def main():
    parser = ArgumentParser(prog="bd-installer")

    _add_args(parser)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    pipeline_dir = os.getenv("BD_PIPELINE_DIR")
    if not pipeline_dir:
        logging.error("Undefined BD_PIPELINE_DIR environment variable. Please activate the pipeline")
        sys.exit(1)

    os.environ["BD_USER"] = os.getenv("BD_USER", getpass.getuser())

    import bd.config as config

    try:
        config.load()
    except BDException as e:
        LOGGER.error(e)
        sys.exit(1)

    if args.which == "install":
        _install(args.name,
                 args.release,
                 args.devel)


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())