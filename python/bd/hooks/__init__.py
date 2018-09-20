__all__ = ["load_hooks", "execute"]

from .registry import *
from .loader import *
from .executor import *


_registry = None


def load_hooks(hook_search_paths=None, loader=HookLoader):
    global _registry

    if _registry is None:
        _registry = HookRegistry()
        loader.load(_registry, hook_search_paths)


def execute(hook_name, *args, **kwargs):
    return HookExecutor(_registry, hook_name, *args, **kwargs)
