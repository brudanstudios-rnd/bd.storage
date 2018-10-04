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

from bd import config
from bd import creator
from bd.logger import get_logger
from bd.exceptions import *

LOGGER = get_logger(__name__)


def _add_args(parser):
    parser.add_argument("toolset_name",
                        help="The name of toolset to create",
                        type=str)
    parser.set_defaults(which="create")


def _create(toolset_name):
    try:
        creator.create(toolset_name)
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)


def main():
    parser = ArgumentParser(prog="bd-create")

    _add_args(parser)

    args = parser.parse_args()

    os.environ["BD_USER"] = os.getenv("BD_USER", getpass.getuser())

    try:
        config.load()
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)

    _create(args.toolset_name)


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())