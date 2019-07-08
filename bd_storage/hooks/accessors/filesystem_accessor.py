import os
import sys
import uuid
import errno
import shutil

from bd_storage.abstract.accessor import Accessor
from bd_storage.logger import get_logger

this = sys.modules[__name__]
this._log = get_logger(__name__)


class FileSystemAccessor(Accessor):

    def __init__(self, root=None):
        self._root = root
        if self._root:
            self._root = root.replace('\\', '/')

    def root(self):
        return self._root

    def resolve(self, uid):
        if not self._root:
            return uid
        return self.join(self._root, uid)

    def read(self, uid):
        filename = self.resolve(uid)
        if not os.path.exists(filename):
            return

        with open(filename, 'rb') as f:
            data = f.read()

        return data

    def write(self, uid, data):
        filename = self.resolve(uid)
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        tmp_filename = '{}__{}'.format(filename, uuid.uuid4().hex)
        try:
            with open(tmp_filename, 'wb') as f:
                f.write(data)

            os.rename(tmp_filename, filename)

        except IOError:
            try:
                os.remove(tmp_filename)
            except IOError:
                pass

    def is_dir(self, uid):
        return os.path.isdir(self.resolve(uid))

    def is_file(self, uid):
        return os.path.isfile(self.resolve(uid))

    def list(self, uid, relative=True, recursive=True):
        paths = []

        initial_dir = self.resolve(uid).rstrip('/')
        start_index = len(initial_dir)

        for root, dirs, files in os.walk(initial_dir):

            dirname = root
            if relative:
                dirname = root[start_index + 1:]

            paths.extend([self.join(dirname, x) for x in files])
            if not recursive:
                continue

        return paths

    def join(self, *args):
        return os.path.join(*args).replace('\\', '/')

    def make_dir(self, uid, recursive=False):
        dirname = self.resolve(uid)
        if recursive:
            try:
                os.makedirs(dirname)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
        else:
            os.mkdir(dirname)

    def rm(self, uid):
        path = self.resolve(uid)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.isfile(path):
            os.unlink(path)

    def exists(self, uid):
        return os.path.exists(self.resolve(uid))


def register(registry):
    registry.add_hook('storage.accessor.init.filesystem-accessor', FileSystemAccessor)
