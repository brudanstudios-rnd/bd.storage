import os
import sys
import uuid
import errno
import shutil
import logging

from ._vendor.six import b, reraise
from .utils import putils
from .errors import *

log = logging.getLogger(__name__)


class BaseAccessor(object):
    def __init__(self, root=None):
        self._root = putils.normpath(root) + '/' if root else None

    def root(self):
        return self._root

    def resolve(self, uid):
        return uid

    def convert_filename_to_uid(self, filename):
        if not self._root:
            return

        if filename.startswith(self._root):
            return filename[len(self._root):]

    def read(self, uid):
        raise NotImplementedError()

    def write(self, uid, data):
        raise NotImplementedError()

    def make_dir(self, uid, recursive=False):
        raise NotImplementedError()

    def exists(self, uid):
        raise NotImplementedError()

    def list(self, uid, relative=False, recursive=True):
        raise NotImplementedError()

    def rm(self, uid):
        raise NotImplementedError()

    def get_filesystem_path(self, uid):
        return


class FileSystemAccessor(BaseAccessor):

    def resolve(self, uid):
        if not self._root:
            return uid
        return putils.join(self._root, uid)

    def read(self, uid):
        filename = self.resolve(uid)
        if not putils.exists(filename):
            return

        with open(filename, 'rb') as f:
            data = f.read()

        return data

    def write(self, uid, data):
        if type(data) is str:
            data = b(data)

        filename = self.resolve(uid)
        try:
            os.makedirs(putils.dirname(filename))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        tmp_filename = '{}__{}'.format(filename, uuid.uuid4().hex)
        try:
            with open(tmp_filename, 'wb') as f:
                f.write(data)
            os.rename(tmp_filename, filename)
        except:
            exc_info = sys.exc_info()

            if putils.exists(tmp_filename):
                try:
                    os.remove(tmp_filename)
                except IOError:
                    log.warning('Unable to remove temporary file "{}"'.format(tmp_filename))

            reraise(*exc_info)

    def list(self, uid, relative=True, recursive=True):
        initial_dir = self.resolve(uid).rstrip('/')
        if not putils.exists(initial_dir):
            raise OSError(errno.ENOENT, 'No such directory: "{}"'.format(initial_dir))

        start_index = len(initial_dir)
        paths = []
        for root, dirs, files in putils.walk(initial_dir):

            dirname = root
            if relative:
                dirname = root[start_index + 1:]

            paths.extend([putils.join(dirname, x) for x in files])

            if not recursive:
                break

        return paths

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
        if putils.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif putils.isfile(path):
            os.unlink(path)

    def exists(self, uid):
        return putils.exists(self.resolve(uid))

    def get_filesystem_path(self, uid):
        return self.resolve(uid)

