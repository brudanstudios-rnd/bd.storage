# -*- coding: utf-8 -*-
import os
import re
from argparse import ArgumentParser
import logging
import getpass

from bd.logger import get_logger

LOGGER = get_logger(__name__)

import bd.config as config
import bd.installer as installer
from bd.exceptions import *


def _add_args(parser):

    parser.add_argument("name",
                        help="The name of toolset to install",
                        type=str)
    parser.add_argument("version",
                        help="Repository version name",
                        type=str)
    parser.set_defaults(which="install")


def _install(name, release):
    return installer.install(name, release)


def main():
    parser = ArgumentParser(prog="bd-install")

    _add_args(parser)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    pipeline_dir = os.getenv("BD_PIPELINE_DIR")
    if not pipeline_dir:
        logging.error("Undefined BD_PIPELINE_DIR environment variable. Please activate the pipeline")
        sys.exit(1)

    os.environ["BD_USER"] = os.getenv("BD_USER", getpass.getuser())

    try:
        config.load()
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)

    sys.exit(not _install(args.name, args.version))


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())