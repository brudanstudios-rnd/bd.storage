def initialize(app_version_dir, environment):
    environment.append("NUKE_PATH", app_version_dir)


def register(registry):
    registry.add_hook("bd.loader.initialize.nuke", initialize)
