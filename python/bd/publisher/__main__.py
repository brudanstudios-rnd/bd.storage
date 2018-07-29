# -*- coding: utf-8 -*-
import os
import re
import sys
from argparse import ArgumentParser
import logging
import getpass

from bd.exceptions import *

LOGGER = logging.getLogger("bd.publisher")

try:
    import git
except Exception as e:
    print "ERROR: Unable to find 'git' command.", e
    sys.exit(1)


def _add_args(parser):
    parser.add_argument("name",
                        help="The name of toolset to publish",
                        type=str)
    parser.add_argument("-r", "--release",
                        help="Repository release(tag) name to clone",
                        type=str)
    parser.set_defaults(which="publish")


def _publish(name, release):
    from bd.publisher import publish
    return publish(name, release)


def main():
    parser = ArgumentParser(prog="bd-publish")

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

    sys.exit(not _publish(args.name, args.release))


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())