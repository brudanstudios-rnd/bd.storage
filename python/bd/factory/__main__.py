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


def _add_args_create(subparsers):
    parser = subparsers.add_parser("create",
                                   help="Create a new toolset")
    parser.add_argument("name",
                        help="The name of toolset to create",
                        type=str)
    parser.set_defaults(which="create")


def _add_args(parser):

    subparsers = parser.add_subparsers()

    _add_args_create(subparsers)


def _create(name):
    from bd.factory import create
    create(name)


def main():
    parser = ArgumentParser(prog="bd-factory")

    _add_args(parser)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    pipeline_dir = os.getenv("BD_PIPELINE_DIR")
    if not pipeline_dir:
        logging.error("Undefined BD_PIPELINE_DIR environment variable. Please activate the pipeline.")
        sys.exit(1)

    os.environ["BD_USER"] = os.getenv("BD_USER", getpass.getuser())

    from bd import config

    if not config.load():
        return

    if args.which == "create":
        _create(args.name)


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())