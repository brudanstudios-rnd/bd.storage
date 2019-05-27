def initialize(app_version_dir, environment):
    for dirname, varname in [("plug-ins", "MAYA_PLUG_IN_PATH"),
                             ("scripts", "MAYA_SCRIPT_PATH"),
                             ("scripts", "PYTHONPATH"),
                             ("icons", "XBMLANGPATH"),
                             ("shelf", "MAYA_SHELF_PATH"),
                             ("presets", "MAYA_PRESET_PATH")]:
        plugins_dir = app_version_dir / dirname
        if plugins_dir.is_dir():
            environment.append(varname, plugins_dir)


def register(registry):
    registry.add_hook("bd.loader.initialize.maya", initialize)
