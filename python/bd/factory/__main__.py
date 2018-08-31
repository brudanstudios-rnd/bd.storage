# -*- coding: utf-8 -*-
import os
import re
import sys
from argparse import ArgumentParser
import logging
import getpass

try:
    import git
except Exception as e:
    print "ERROR: Unable to find 'git' command.", e
    sys.exit(1)

import bd.config as config
import bd.factory as factory
from bd.exceptions import *

LOGGER = logging.getLogger(__name__)


def _add_args(parser):
    parser.add_argument("toolset_name",
                        help="The name of toolset to create",
                        type=str)
    parser.set_defaults(which="create")


def _create(name):
    try:
        factory.create(name)
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)


def main():
    parser = ArgumentParser(prog="bd-create")

    _add_args(parser)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    pipeline_dir = os.getenv("BD_PIPELINE_DIR")
    if not pipeline_dir:
        LOGGER.error("Undefined BD_PIPELINE_DIR environment variable. Please activate the pipeline.")
        sys.exit(1)

    os.environ["BD_USER"] = os.getenv("BD_USER", getpass.getuser())

    try:
        config.load()
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)

    _create(args.name)


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())