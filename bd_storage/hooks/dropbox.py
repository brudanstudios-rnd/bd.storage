import os
import sys
import shutil
import logging

from bd_storage.accessor.base import Accessor

this = sys.modules[__name__]
this._log = logging.getLogger(__name__.replace('bd_storage', 'bd'))


class DropboxAccessor(Accessor):

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

    def write(self, uid, data):
        with open(self.resolve(uid), "wb") as f:
            return f.write(data)

    def read(self, uid):
        with open(self.resolve(uid), "rb") as f:
            return f.read()

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

    def get_filesystem_path(self, uid, mode):
        return


def register(registry):
    registry.add_hook('storage.accessor.init.fs-dropbox-accessor', DropboxAccessor.new)
