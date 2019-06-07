import os
import sys
import shutil
import logging

from bd_storage.accessor.base import Accessor

this = sys.modules[__name__]
this._log = logging.getLogger(__name__.replace('bd_storage', 'bd'))


class MedusaAccessor(Accessor):

    def __init__(self, root):
        self._root = root
        if self._root:
            self._root = root.replace('\\', '/')

    @classmethod
    def new(cls, **kwargs):
        root = kwargs.get("root")
        return cls(root)

    def resolve(self, uid):
        if not self._root:
            return uid
        return '/'.join([self._root, uid])

    def open(self, uid, mode):
        if 'r' in mode and not self.exists(uid):
            return

        filename = self.resolve(uid)

        if 'w' in mode:
            try:
                os.makedirs(os.path.dirname(filename))
            except OSError:
                pass

        return open(filename, mode)

    def make_dir(self, uid):
        os.mkdir(self.resolve(uid))

    def rm(self, uid):
        path = self.resolve(uid)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.isfile(path):
            os.unlink(path)

    def exists(self, uid):
        return os.path.exists(self.resolve(uid))


def register(registry):
    registry.add_hook('storage.accessor.init.fs-medusa-accessor', MedusaAccessor.new)
