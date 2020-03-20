import os
import sys
import uuid
import errno
import shutil
import logging

from ._vendor.six import b, u
from .abstract.accessor import Accessor

this = sys.modules[__name__]
this._log = logging.getLogger(__name__)


class FileSystemAccessor(Accessor):

    def __init__(self, root=None):
        self._root = root
        if self._root:
            self._root = root.replace('\\', '/') + '/'

    def resolve(self, uid):
        if not self._root:
            return uid
        return self._join(self._root, uid)

    def read(self, uid):
        filename = self.resolve(uid)
        if not os.path.exists(filename):
            return

        with open(filename, 'rb') as f:
            data = f.read()

        return data

    def write(self, uid, data):
        if type(data) is str:
            data = b(data)
            
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

    def list(self, uid, relative=True, recursive=True):
        paths = []

        initial_dir = self.resolve(uid).rstrip('/')
        start_index = len(initial_dir)

        for root, dirs, files in os.walk(initial_dir):

            dirname = root
            if relative:
                dirname = root[start_index + 1:]

            paths.extend([self._join(dirname, x) for x in dirs])
            paths.extend([self._join(dirname, x) for x in files])

            if not recursive:
                break

        return paths

    def _join(self, *args):
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

    def get_filename(self, uid):
        return self.resolve(uid)

