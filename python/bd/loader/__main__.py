# -*- coding: utf-8 -*-
import os
import re
import sys
from argparse import ArgumentParser
import logging
import getpass

import bd.config as config
from bd.loader.environment import ENV
from bd.exceptions import *

LOGGER = logging.getLogger(__name__)


def _add_args_load(subparsers):
    parser = subparsers.add_parser("load",
                                   help="Find and load all toolsets")
    _add_common_args(parser)

    parser.add_argument("app_name",
                        help=("The name of the app to load "
                              "modules for (e.g. houdini, maya, ...)"),
                        type=str)
    parser.add_argument("-v", "--app-version",
                        help=("The apps with version lower than this "
                              "will be ignored e.g. 2016, 15.5.300, ..."),
                        type=str)
    parser.add_argument("--print-environment",
                        help="Make the command output redirected to stdout",
                        action="store_true")

    parser.add_argument("--dump-environment",
                        help="Write a pickled environment to this file",
                        type=str)
    parser.add_argument("--devel",
                        help="Switch to a development mode",
                        action="store_true")
    parser.set_defaults(which="load")


def _add_args_list(subparsers):
    parser = subparsers.add_parser("list",
                                   help="List all toolsets available for loading")

    _add_common_args(parser)

    parser.add_argument("--devel",
                        help="Switch to a development mode",
                        action="store_true")
    parser.set_defaults(which="list")


def _load(app_name,
          app_version,
          print_environment,
          dump_environment,
          devel):

    from bd.loader import load_toolsets
    import cPickle

    if not load_toolsets(app_name, app_version, devel):
        sys.exit(1)

    if dump_environment:
        with open(dump_environment, "w") as f:
            cPickle.dump(ENV.to_dict(), f)

    if print_environment:
        for key, value in ENV.to_dict().iteritems():
            cmd_template = "set {}={}" if sys.platform == "win32" else "export {}='{}'"
            print cmd_template.format(key, value)


def _list(devel):
    from bd.loader import list_toolsets
    list_toolsets(devel)


def _add_common_args(parser):
    parser.add_argument("-u", "--user", type=str,
                        help="Run as a specific user")


def _add_args(parser):
    subparsers = parser.add_subparsers()

    _add_args_load(subparsers)
    _add_args_list(subparsers)


def main():
    parser = ArgumentParser(prog="bd-loader")

    _add_args(parser)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    pipeline_dir = os.getenv("BD_PIPELINE_DIR")
    if not pipeline_dir:
        LOGGER.error("Undefined BD_PIPELINE_DIR environment variable. Please activate the pipeline")
        sys.exit(1)

    user = os.getenv("BD_USER", getpass.getuser())
    ENV["BD_USER"] = args.user if args.user else user

    if not os.getenv("BD_PRESET_NAME"):
        LOGGER.error("Please specify a project preset name.")
        sys.exit(1)

    try:
        config.load()
    except Error as e:
        LOGGER.error(e)
        sys.exit(1)

    if args.which == "load":
        _load(args.app_name,
              args.app_version,
              args.print_environment,
              args.dump_environment,
              args.devel)

    elif args.which == "list":
        _list(args.devel)


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(main())