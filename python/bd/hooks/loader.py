__all__ = ["HookLoader"]

import os

from pluginbase import PluginBase


def get_searchpath(path):

    paths = [path]

    for entry in os.listdir(path):

        entry_path = os.path.join(path, entry)

        if not os.path.isdir(entry_path):
            continue

        paths.extend(get_searchpath(entry_path))

    return paths


class HookLoader(object):

    _plugin_source = None

    @classmethod
    def load(cls, registry, hook_search_paths=None):
        if not hook_search_paths:
            hook_search_paths = []

            BD_HOOKPATH = os.getenv("BD_HOOKPATH")
            if not BD_HOOKPATH:
                return

            hook_search_paths.extend(BD_HOOKPATH.split(os.pathsep))
        else:
            hook_search_paths = map(str, hook_search_paths)

        deep_search_paths = []
        for hook_search_path in hook_search_paths:
            deep_search_paths.extend(get_searchpath(hook_search_path))

        plugin_base = PluginBase(package="bd.hooks")
        cls._plugin_source = plugin_base.make_plugin_source(searchpath=deep_search_paths)

        for plugin_name in cls._plugin_source.list_plugins():
            plugin = cls._plugin_source.load_plugin(plugin_name)
            plugin.register(registry)