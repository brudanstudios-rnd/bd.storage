__all__ = ["HookLoader"]

import os

from pluginbase import PluginBase

from ..exceptions import *


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
        if hook_search_paths is None:
            hook_search_paths = []

        hook_search_paths = map(str, hook_search_paths)

        BD_HOOKPATH = os.getenv("BD_HOOKPATH")
        if BD_HOOKPATH:
            hook_search_paths.extend(BD_HOOKPATH.split(os.pathsep))

        if not hook_search_paths:
            raise SearchPathsNotDefinedError()

        deep_search_paths = []
        for hook_search_path in hook_search_paths:
            if os.path.exists(hook_search_path):
                try:
                    deep_search_paths.extend(get_searchpath(hook_search_path))
                except OSError as e:
                    continue

        if not deep_search_paths:
            return

        plugin_base = PluginBase(package="bd.hooks")

        cls._plugin_source = plugin_base.make_plugin_source(searchpath=deep_search_paths)

        for plugin_name in cls._plugin_source.list_plugins():
            try:
                plugin = cls._plugin_source.load_plugin(plugin_name)
            except Exception as e:
                raise HookLoadingError(details={"path": plugin_name,
                                                "exc_msg": str(e)})
            try:
                plugin.register(registry)
            except Exception as e:
                raise HookRegistrationError(details={"path": plugin_name,
                                                     "exc_msg": str(e)})

    @classmethod
    def clean(cls):
        cls._plugin_source = None