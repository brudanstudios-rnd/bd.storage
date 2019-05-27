def initialize(app_version_dir, environment):
    environment.append("PYTHONPATH", app_version_dir)


def register(registry):
    registry.add_hook("bd.loader.initialize.python", initialize)
