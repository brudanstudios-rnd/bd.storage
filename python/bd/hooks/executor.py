import logging
from ..exceptions import CallbackExecutionError

LOGGER = logging.getLogger(__name__)


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
            else:
                return callback(obj_weakref(), *self._args, **self._kwargs)
        except Exception as e:
            raise CallbackExecutionError(details={"hook_name": self._hook_name,
                                                  "callback": str(callback),
                                                  "exc_msg": str(e)})

    def all(self, result_callback=None):

        hook_infos = self._registry.get_hooks(self._hook_name)

        for hook_info in hook_infos:

            result = self._exec_single(hook_info)

            if result_callback:
                result_callback(result)

    def one(self):

        hook_infos = self._registry.get_hooks(self._hook_name)

        return self._exec_single(hook_infos[0])