import os
import sys
import uuid
import socket
import ftplib
try:
    import StringIO
except ImportError:
    from io import StringIO

from bd_storage.abstract.accessor import Accessor
from bd.secrets import get_secret

from bd_storage.logger import get_logger

this = sys.modules[__name__]
this._log = get_logger(__name__)

socket.setdefaulttimeout(None)


class FTPAccessor(Accessor):

    def __init__(self, root=None):
        self._root = root
        if self._root:
            self._root = root.replace('\\', '/')

        self._connect()

    def _connect(self):
        self._ftp = ftplib.FTP()
        self._ftp.debug(0)
        self._ftp.set_pasv(True)

        self._ftp.connect(get_secret()['FTP_HOST'])
        self._ftp.login(
            get_secret()['FTP_LOGIN'],
            get_secret()['FTP_PASSWORD'],
        )

    def root(self):
        return self._root

    def resolve(self, uid):
        if not self._root:
            return uid
        return self.join(self._root, uid)

    def read(self, uid):
        data_buffer = StringIO.StringIO()
        self._ftp.retrbinary('RETR {}'.format(uid), data_buffer.write)
        return data_buffer.getvalue()

    def write(self, uid, data):
        parent_dir = os.path.dirname(uid)
        if not self.exists(parent_dir):
            self.make_dir(parent_dir, recursive=True)

        tmp_filename = '{}__{}'.format(uid, uuid.uuid4().hex)

        data_buffer = StringIO.StringIO(data)

        try:
            self._ftp.storbinary('STOR {}'.format(tmp_filename), data_buffer)
            self._ftp.rename(tmp_filename, uid)
        finally:
            data_buffer.close()

    def is_dir(self, uid):
        pwd = self._ftp.pwd()
        try:
            self._ftp.cwd(uid)
            return True
        except:
            return False
        finally:
            self._ftp.cwd(pwd)

    def is_file(self, uid):
        if not self.exists(uid):
            return False

        return not self.is_dir(uid)

    def _traverse(self):
        data = []
        current_dir = self._ftp.pwd()
        for entry in (path for path in self._ftp.nlst() if path not in ('.', '..')):
            try:
                self._ftp.cwd(entry)
                data.extend(self._traverse())
                self._ftp.cwd('..')
            except ftplib.error_perm:
                data.append('{}/{}'.format(current_dir, entry))
        return data

    def list(self, uid, relative=True, recursive=True):
        initial_dir = uid.rstrip('/')

        try:
            self._ftp.cwd(initial_dir)
        except ftplib.error_perm:
            return []

        try:
            if recursive:
                start_index = len(initial_dir)
                return [
                    path[start_index + 1:] if relative else path
                    for path in self._traverse()
                    if path not in ['.', '..']
                ]

            try:
                return [
                    entry if relative else '{}/{}'.format(initial_dir, entry)
                    for entry in self._ftp.nlst()
                    if entry not in ('.', '..')
                ]
            except ftplib.error_perm:
                return []
        finally:
            self._ftp.cwd('/')

    def join(self, *args):
        return os.path.join(*args).replace('\\', '/')

    def make_dir(self, uid, recursive=False):
        if recursive:
            for dir_chunk in uid.split('/'):
                self._ftp.mkd(dir_chunk)
                self._ftp.cwd(dir_chunk)
            self._ftp.cwd('/')
        else:
            self._ftp.mkd(uid)

    def rm(self, uid):
        if self.is_dir(uid):
            self._ftp.rmd(uid)
        elif self.is_file(uid):
            self._ftp.delete(uid)

    def exists(self, uid):
        try:
            files = self._ftp.nlst(os.path.dirname(uid))
            return uid in files
        except:
            return False

    def __del__(self):
        self._ftp.close()


def register(registry):
    registry.add_hook('storage.accessor.init.ftp-accessor', FTPAccessor)
