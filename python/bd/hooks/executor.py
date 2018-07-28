import logging

LOGGER = logging.getLogger("bd.hooks.registry")


class HookExecutor(object):

    def __init__(self, registry, hook_name, *args, **kwargs):
        self._registry = registry
        self._hook_name = hook_name
        self._args = args
        self._kwargs = kwargs


    def _exec_single(self, hook_info):

        _, callback, obj_weakref = hook_info

        try:
            if obj_weakref is None:  # is a function
                return callback(*self._args, **self._kwargs)

            else:  # is a method
                if obj_weakref() is None:  # object is dead

                    self._registry.pop(self._hook_name)

                    LOGGER.error("The callback owner for the "
                                 "hook '{}' is dead".format(self._hook_name))
                else:
                    return callback(obj_weakref(), *self._args, **self._kwargs)
        except:
            LOGGER.error("Failed to execute callback for hook: {}".format(self._hook_name))
            raise

    def all(self, result_callback=None):

        hook_infos = self._registry.get_hooks(self._hook_name)

        if hook_infos is None:
            LOGGER.error("Unable to find a hook: '{}'".format(self._hook_name))
            return

        for hook_info in hook_infos:

            result = self._exec_single(hook_info)

            if result_callback:
                result_callback(result)

    def one(self):

        hook_infos = self._registry.get_hooks(self._hook_name)

        if hook_infos is None:
            LOGGER.error("Unable to find a hook: '{}'".format(self._hook_name))
            return

        return self._exec_single(hook_infos[0])