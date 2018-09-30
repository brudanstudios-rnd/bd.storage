# -*- coding: utf-8 -*-
import os
import re
import sys
from argparse import ArgumentParser
import logging
import getpass

from bd.logger import get_logger
from bd import config
from bd.exceptions import *

LOGGER = get_logger(__name__)

try:
    import git
except Exception as e:
    print "ERROR: Unable to find 'git' command.", e
    sys.exit(1)


def _add_args(parser):
    parser.add_argument("toolset_name",
                        help="The name of toolset to create",
                        type=str)
    parser.set_defaults(which="create")


def _publish():
    from bd.publisher import publish
    return publish()


def main():
    parser = ArgumentParser(prog="bd-publish")

    parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    os.environ["BD_USER"] = os.getenv("BD_USER", getpass.getuser())

    try:
        config.load()
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)

    sys.exit(not _publish())


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())