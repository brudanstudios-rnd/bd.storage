import os
import sys
import uuid
import errno
import shutil
import logging

from six import b, reraise

from .utils import putils
from .errors import *

log = logging.getLogger(__name__)


class BaseAccessor(object):
    def __init__(self, root=None):
        self._root = putils.normpath(root) + "/" if root else None

    def root(self):
        return self._root

    def resolve(self, rpath):
        return rpath

    def convert_filename_to_rpath(self, filename):
        if not self._root:
            return

        if filename.startswith(self._root):
            return filename[len(self._root) :]

    def read(self, rpath):
        raise NotImplementedError()

    def write(self, rpath, data):
        raise NotImplementedError()

    def make_dir(self, rpath, recursive=False):
        raise NotImplementedError()

    def exists(self, rpath):
        raise NotImplementedError()

    def list(self, rpath, relative=False, recursive=True):
        raise NotImplementedError()

    def rm(self, rpath):
        raise NotImplementedError()

    def get_filesystem_path(self, rpath):
        return


class FileSystemAccessor(BaseAccessor):
    def resolve(self, rpath):
        if not self._root:
            return rpath
        return putils.join(self._root, rpath)

    def read(self, rpath):
        filename = self.resolve(rpath)
        if not putils.exists(filename):
            return

        with open(filename, "rb") as f:
            data = f.read()

        return data

    def write(self, rpath, data):
        if type(data) is str:
            data = b(data)

        filename = self.resolve(rpath)
        try:
            os.makedirs(putils.dirname(filename))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        tmp_filename = "{}__{}".format(filename, uuid.uuid4().hex)
        try:
            with open(tmp_filename, "wb") as f:
                f.write(data)
            os.replace(tmp_filename, filename)
        except:
            exc_info = sys.exc_info()

            if putils.exists(tmp_filename):
                try:
                    os.remove(tmp_filename)
                except IOError:
                    log.warning(
                        'Unable to remove temporary file "{}"'.format(tmp_filename)
                    )

            reraise(*exc_info)

    def list(self, rpath, relative=True, recursive=True):
        initial_dir = self.resolve(rpath).rstrip("/")
        if not putils.exists(initial_dir):
            raise OSError(errno.ENOENT, 'No such directory: "{}"'.format(initial_dir))

        start_index = len(initial_dir)
        paths = []
        for root, dirs, files in putils.walk(initial_dir):

            dirname = root
            if relative:
                dirname = root[start_index + 1 :]

            paths.extend([putils.join(dirname, x) for x in files])

            if not recursive:
                paths.extend([putils.join(dirname, x) for x in dirs])
                break

        return paths

    def make_dir(self, rpath, recursive=False):
        dirname = self.resolve(rpath)
        if recursive:
            try:
                os.makedirs(dirname)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
        else:
            os.mkdir(dirname)

    def rm(self, rpath):
        path = self.resolve(rpath)
        if putils.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif putils.isfile(path):
            os.unlink(path)

    def exists(self, rpath):
        return putils.exists(self.resolve(rpath))

    def get_filesystem_path(self, rpath):
        return self.resolve(rpath)
