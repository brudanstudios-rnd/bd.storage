__all__ = ["HookRegistry"]

import weakref
import types
import logging


LOGGER = logging.getLogger("bd.hooks.registry")


class HookRegistry(object):

    def __init__(self):
        self._hooks = {}
        self._sorted = set()
        self._forced_solo = set()

    def add_hook(self, name, callback, priority=50, force_solo=False):

        if not force_solo and name in self._forced_solo:
            return

        LOGGER.debug("Adding hook: {} ...".format(name))

        if force_solo:
            self._forced_solo.add(name)
            hooks = []
        else:
            hooks = self._hooks.get(name, [])

        if isinstance(callback, types.FunctionType):
            hook = (priority, callback, None)
        else:
            hook = (priority, callback.im_func,
                    weakref.ref(callback.im_self))

        hooks.append(hook)

        self._hooks[name] = hooks

        LOGGER.debug("Done")

    def get_hooks(self, name):
        hooks = self._hooks.get(name)

        if not hooks:
            return

        if name not in self._sorted:
            hooks.sort(key=lambda x: x[0], reverse=True)
            self._sorted.add(name)

        return hooks