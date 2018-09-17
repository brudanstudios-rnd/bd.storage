__all__ = ["HookRegistry"]

import weakref
import types

from ..logger import get_logger
from ..exceptions import InvalidCallbackError, HookNotFoundError, HookCallbackDeadError

LOGGER = get_logger()


class HookRegistry(object):

    def __init__(self):
        self._hooks = {}
        self._sorted = set()
        self._forced_solo = set()

    def add_hook(self, name, callback, priority=50, force_solo=False):
        if not callable(callback):
            raise InvalidCallbackError(details={"hook_name": name,
                                                "callback": str(callback)})

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
            raise HookNotFoundError(details={"hook_name": name})

        # remove all the method callbacks bound to the deleted objects
        for i in range(len(hooks)-1, -1, -1):

            _, callback, obj_weakref = hooks[i]

            # chech if it is a method and the owner is dead
            if obj_weakref is not None and obj_weakref() is None:
                del hooks[i]

        # remove this hook from the registry
        # if there is no callbacks left
        if not hooks:
            del self._hooks[name]
            if name in self._sorted:
                self._sorted.remove(name)
            if name in self._forced_solo:
                self._forced_solo.remove(name)
            raise HookCallbackDeadError(details={"hook_name": name})

        if name not in self._sorted:
            hooks.sort(key=lambda x: x[0], reverse=True)
            self._sorted.add(name)

        return hooks