import sys


def initialize(app_version_dir, environment):
    environment.append("HOUDINI_PATH", app_version_dir)


def finalize(environment):
    symbol = "^&" if sys.platform == "win32" else "&"
    houdini_path = environment.getenv("HOUDINI_PATH")
    if not houdini_path:
        environment.putenv("HOUDINI_PATH", symbol)
    elif symbol not in houdini_path:
        environment.append("HOUDINI_PATH", symbol)


def register(registry):
    registry.add_hook("bd.loader.initialize.houdini", initialize)
    registry.add_hook("bd.loader.finalize", finalize)
