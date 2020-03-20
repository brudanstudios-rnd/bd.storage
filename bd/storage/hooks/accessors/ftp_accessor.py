import os
import sys
import uuid
import socket
import ftplib
import logging
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from bd.storage._vendor.six import BytesIO
from bd.storage.abstract.accessor import Accessor

this = sys.modules[__name__]
this._log = logging.getLogger(__name__)


class FTPAccessor(Accessor):

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
        self._write_mode = write_mode
        self._ftp = None

        self._ensure_connected()

    def _ensure_connected(self):
        if self._ftp is None:
            self._ftp = ftplib.FTP()
            self._ftp.debug(0)
            self._ftp.set_pasv(True)

        try:
            self._ftp.voidcmd('NOOP')  # check ftp connection
        except:
            try:
                self._ftp.connect(self._host, timeout=self._timeout)
                self._ftp.login(
                    self._username,
                    self._password,
                )
            except Exception as e:
                this._log.error(
                    'Unable to connect to "{}" due to error: {}'.format(
                        self._host, str(e)
                    )
                )
                return False

        return True

    def _get_local_path(self, remote_path):
        return os.path.join(self._root, remote_path)

    def _get_transit_path(self, target_path):
        return '{}__{}'.format(
            '/.'.join(os.path.split(target_path)),
            uuid.uuid1().hex
        )

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

    # def read(self, uid):
    #     if not self._ensure_connected():
    #         return False

    #     data_buffer = BytesIO()
        
    #     try:
    #         self._ftp.retrbinary('RETR {}'.format(uid), data_buffer.write)
    #     except (socket.error, IOError, ftplib.all_errors) as e:
    #         this._log.error(
    #             'Unable to read data from \'{}\'. {}'.format(uid, str(e))
    #         )
    #         return

    #     return data_buffer.getvalue()

    def write(self, uid, data):
        if not self._ensure_connected():
            return False

        transit_path = self._get_transit_path(uid)

        data_buffer = BytesIO(data)

        success = False

        try:
            parent_dir = os.path.dirname(uid)
            if not self.exists(parent_dir):
                self.make_dir(parent_dir, recursive=True)

            # write to transit file
            self._ftp.storbinary('STOR {}'.format(transit_path), data_buffer)
        except Exception as e:
            this._log.error(
                'Unable to write data to file: \'{}\'. {}'.format(
                    self._get_local_path(transit_path),
                    str(e)
                )
            )
        else:
            try:
                # set permissions on transit file
                self._ftp.sendcmd('SITE CHMOD {} {}'.format(
                    str(self._write_mode), transit_path)
                )
                # rename transit path to the final path
                self._ftp.rename(transit_path, uid)
            except Exception as e:
                this._log.error(
                    'Unable to rename \'{}\' to \'{}\'. {}'.format(
                        self._get_local_path(transit_path),
                        uid,
                        str(e)
                    )
                )
            else:
                success = True
        finally:
            try:
                self._ftp.delete(transit_path)
            except Exception:
                pass

        return success

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
                data.extend(self._traverse())
                self._ftp.cwd('..')
            except ftplib.error_perm:
                data.append('{}/{}'.format(current_dir, entry))
        return data

    def list(self, uid, relative=True, recursive=True):
        if not self._ensure_connected():
            return []

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
        if not self._ensure_connected():
            return False

        if recursive:
            for dir_chunk in uid.split('/'):
                try:
                    self._ftp.cwd(dir_chunk)
                except:
                    self._ftp.mkd(dir_chunk)
                    self._ftp.cwd(dir_chunk)
            self._ftp.cwd('/')
        else:
            self._ftp.mkd(uid)

    def rm(self, uid):
        if not self._ensure_connected():
            return False
        
        try:
            if self._is_dir(uid):
                self._ftp.rmd(uid)
            elif self._is_file(uid):
                self._ftp.delete(uid)
        except Exception as e:
            this._log.error(
                "Unable to remove remote path '{}'. {}".format(uid, str(e))
            )
            return False

        return True

    def exists(self, uid):
        if not self._ensure_connected():
            return False

        try:
            files = self._ftp.nlst(os.path.dirname(uid))
            return uid in files
        except Exception:
            return False

    def get_filename(self, uid):
        return self.resolve(uid)
        
    def __del__(self):
        self._ftp.close()


def register(registry):
    registry.add_hook('ftp-accessor', FTPAccessor)
