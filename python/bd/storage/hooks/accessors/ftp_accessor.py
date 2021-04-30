import sys
import uuid
import ftplib
import logging

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from six import BytesIO, reraise

from bd.storage.accessor import BaseAccessor, FileSystemAccessor
from bd.storage.utils import putils
from bd.storage.errors import *

log = logging.getLogger(__name__)


class FTPAccessor(BaseAccessor):

    def __init__(
            self,
            root=None,
            host=None,
            username=None,
            password=None,
            timeout=None,
            write_mode=775
    ):

        super(FTPAccessor, self).__init__(root)

        self._host = host
        self._username = username
        self._password = password
        self._timeout = timeout

        self._fs_accessor = None
        if root:
            self._fs_accessor = FileSystemAccessor(root)

        self._write_mode = write_mode
        self._ftp = None

    def _ensure_connected(self):
        if self._ftp is None:
            self._ftp = ftplib.FTP()
            self._ftp.debug(0)
            self._ftp.set_pasv(True)

        try:
            self._ftp.voidcmd('NOOP')  # check ftp connection
        except:
            self._ftp.connect(self._host, timeout=self._timeout)
            self._ftp.login(
                self._username,
                self._password,
            )

    def _get_transit_path(self, target_path):
        return '{}__{}'.format(
            '/.'.join(putils.split(target_path)),
            uuid.uuid1().hex
        )

    def resolve(self, uid):
        if not self._root:
            return uid
        return putils.join(self._root, uid)

    def read(self, uid):
        if self._fs_accessor:
            data = self._fs_accessor.read(uid)
        else:
            self._ensure_connected()

            data_buffer = BytesIO()

            try:
                self._ftp.retrbinary('RETR {}'.format(uid), data_buffer.write)
            except ftplib.error_perm as e:

                # if file doesn't exist
                if e.message[:3] == '550':
                    return

                raise

            data = data_buffer.getvalue()

        return data

    def write(self, uid, data):
        self._ensure_connected()

        transit_path = self._get_transit_path(uid)

        data_buffer = BytesIO(data)

        try:
            parent_dir = putils.dirname(uid)
            if not self.exists(parent_dir):
                self.make_dir(parent_dir, recursive=True)

            # write to transit file
            self._ftp.storbinary('STOR {}'.format(transit_path), data_buffer)

            # set permissions on transit file
            try:
                self._ftp.sendcmd('SITE CHMOD {} {}'.format(
                    str(self._write_mode), transit_path)
                )
            except ftplib.error_perm as e:
                # CHMODE command is not implemented
                # if the server is running on windows
                if e.message[:3] != '504':
                    raise

            # rename transit path to the final path
            self._ftp.rename(transit_path, uid)
        finally:
            try:
                if self.exists(transit_path):
                    self._ftp.delete(transit_path)
            except:
                pass

    def _is_dir(self, uid):
        pwd = self._ftp.pwd()
        try:
            self._ftp.cwd(uid)
            return True
        except:
            return False
        finally:
            self._ftp.cwd(pwd)

    def _is_file(self, uid):
        if not self.exists(uid):
            return False

        return not self._is_dir(uid)

    def _traverse(self):
        data = []
        current_dir = self._ftp.pwd()
        for entry in (path for path in self._ftp.nlst() if path not in ('.', '..')):
            try:
                self._ftp.cwd(entry)
            except ftplib.error_perm as e:

                # we get here only if cwd command failed
                # it fails when the path is a file
                if e.message[:3] != '550':
                    raise

                data.append(putils.join(current_dir, entry))
            else:
                data.extend(self._traverse())
                self._ftp.cwd('..')

        return data

    def list(self, uid, relative=True, recursive=True):
        if self._fs_accessor:
            return self._fs_accessor.list(uid, relative, recursive)
        else:
            self._ensure_connected()

            initial_dir = uid.rstrip('/')

            self._ftp.cwd(initial_dir)

            try:
                if recursive:
                    start_index = len(initial_dir)
                    return [
                        path[start_index + 1:] if relative else path
                        for path in self._traverse()
                        if path not in ['.', '..']
                    ]

                return [
                    entry if relative else putils.join(initial_dir, entry)
                    for entry in self._ftp.nlst()
                    if entry not in ('.', '..')
                ]
            finally:
                self._ftp.cwd('/')

    def make_dir(self, uid, recursive=False):
        self._ensure_connected()

        self._ftp.cwd('/')

        if recursive:
            for dir_chunk in uid.split('/'):
                try:
                    self._ftp.cwd(dir_chunk)
                except ftplib.error_perm as e:

                    # reraise any error except when directory not found
                    if e.message[:3] != '550':
                        raise

                    self._ftp.mkd(dir_chunk)
                    self._ftp.cwd(dir_chunk)

            self._ftp.cwd('/')
        else:
            self._ftp.mkd(uid)

    def rm(self, uid):
        self._ensure_connected()

        if self._is_dir(uid):
            current_dir = self._ftp.pwd()

            for nested_path in self._ftp.nlst(uid):
                if putils.split(nested_path)[1] in ('.', '..'):
                    continue

                try:
                    self._ftp.cwd(nested_path)  # if we can cwd to it, it's a folder
                except ftplib.error_perm as e:

                    # reraise any error except when directory not found
                    if e.message[:3] != '550':
                        raise

                    self._ftp.delete(nested_path)
                else:
                    self._ftp.cwd(current_dir)  # don't try to remove a folder we're in
                    self.rm(nested_path)

            self._ftp.rmd(uid)

        elif self._is_file(uid):
            self._ftp.delete(uid)

    def exists(self, uid):
        if self._fs_accessor:
            return self._fs_accessor.exists(uid)
        else:
            self._ensure_connected()

            try:
                files = self._ftp.nlst(putils.dirname(uid))
                return uid in files
            except ftplib.error_perm as e:

                if e.message[:3] != '550':
                    raise

                return False

    def get_filesystem_path(self, uid):
        return self._fs_accessor.get_filesystem_path(uid) if self._fs_accessor else None

    def __del__(self):
        try:
            self._ftp.close()
        except:
            pass


def register(registry):
    registry.add_hook('ftp', FTPAccessor)
