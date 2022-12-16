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
        write_mode=775,
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
            self._ftp.voidcmd("NOOP")  # check ftp connection
        except:
            self._ftp.connect(self._host, timeout=self._timeout)
            self._ftp.login(
                self._username,
                self._password,
            )

    def _get_transit_path(self, target_path):
        return "{}__{}".format("/.".join(putils.split(target_path)), uuid.uuid1().hex)

    def resolve(self, rpath):
        if not self._root:
            return rpath
        return putils.join(self._root, rpath)

    def read(self, rpath):
        if self._fs_accessor:
            data = self._fs_accessor.read(rpath)
        else:
            self._ensure_connected()

            data_buffer = BytesIO()

            try:
                self._ftp.retrbinary("RETR {}".format(rpath), data_buffer.write)
            except ftplib.error_perm as e:

                # if file doesn't exist
                if str(e)[:3] == "550":
                    return

                raise

            data = data_buffer.getvalue()

        return data

    def write(self, rpath, data):
        self._ensure_connected()

        transit_path = self._get_transit_path(rpath)

        try:
            data = data.encode("utf-8")
        except AttributeError:
            pass

        data_buffer = BytesIO(data)

        try:
            parent_dir = putils.dirname(rpath)
            if not self.exists(parent_dir):
                self.make_dir(parent_dir, recursive=True)

            # write to transit file
            self._ftp.storbinary("STOR {}".format(transit_path), data_buffer)

            # set permissions on transit file
            try:
                self._ftp.sendcmd(
                    "SITE CHMOD {} {}".format(str(self._write_mode), transit_path)
                )
            except ftplib.error_perm as e:
                # CHMODE command is not implemented
                # if the server is running on windows
                if str(e)[:3] != "504":
                    raise

            # rename transit path to the final path
            self._ftp.rename(transit_path, rpath)
        finally:
            try:
                if self.exists(transit_path):
                    self._ftp.delete(transit_path)
            except:
                pass

    def _is_dir(self, rpath):
        pwd = self._ftp.pwd()
        try:
            self._ftp.cwd(rpath)
            return True
        except:
            return False
        finally:
            self._ftp.cwd(pwd)

    def _is_file(self, rpath):
        if not self.exists(rpath):
            return False

        return not self._is_dir(rpath)

    def _traverse(self):
        data = []
        current_dir = self._ftp.pwd()
        for entry in (path for path in self._ftp.nlst() if path not in (".", "..")):
            try:
                self._ftp.cwd(entry)
            except ftplib.error_perm as e:

                # we get here only if cwd command failed
                # it fails when the path is a file
                if str(e)[:3] != "550":
                    raise

                data.append(putils.join(current_dir, entry))
            else:
                data.extend(self._traverse())
                self._ftp.cwd("..")

        return data

    def list(self, rpath, relative=True, recursive=True):
        if self._fs_accessor:
            return self._fs_accessor.list(rpath, relative, recursive)
        else:
            self._ensure_connected()

            initial_dir = rpath.rstrip("/")

            self._ftp.cwd(initial_dir)

            try:
                if recursive:
                    start_index = len(initial_dir)
                    return [
                        path[start_index + 1 :] if relative else path
                        for path in self._traverse()
                        if path not in [".", ".."]
                    ]

                return [
                    entry if relative else putils.join(initial_dir, entry)
                    for entry in self._ftp.nlst()
                    if entry not in (".", "..")
                ]
            finally:
                self._ftp.cwd("/")

    def make_dir(self, rpath, recursive=False):
        self._ensure_connected()

        self._ftp.cwd("/")

        if recursive:
            for dir_chunk in rpath.split("/"):
                try:
                    self._ftp.cwd(dir_chunk)
                except ftplib.error_perm as e:

                    # reraise any error except when directory not found
                    if str(e)[:3] != "550":
                        raise

                    self._ftp.mkd(dir_chunk)
                    self._ftp.cwd(dir_chunk)

            self._ftp.cwd("/")
        else:
            self._ftp.mkd(rpath)

    def rm(self, rpath):
        self._ensure_connected()

        if self._is_dir(rpath):
            current_dir = self._ftp.pwd()

            for nested_path in self._ftp.nlst(rpath):
                if putils.split(nested_path)[1] in (".", ".."):
                    continue

                try:
                    self._ftp.cwd(nested_path)  # if we can cwd to it, it's a folder
                except ftplib.error_perm as e:

                    # reraise any error except when directory not found
                    if str(e)[:3] != "550":
                        raise

                    self._ftp.delete(nested_path)
                else:
                    self._ftp.cwd(current_dir)  # don't try to remove a folder we're in
                    self.rm(nested_path)

            self._ftp.rmd(rpath)

        elif self._is_file(rpath):
            self._ftp.delete(rpath)

    def exists(self, rpath):
        if self._fs_accessor:
            return self._fs_accessor.exists(rpath)
        else:
            self._ensure_connected()

            try:
                files = self._ftp.nlst(putils.dirname(rpath))
                return rpath in files
            except ftplib.error_perm as e:

                if str(e)[:3] != "550":
                    raise

                return False

    def get_filesystem_path(self, rpath):
        return (
            self._fs_accessor.get_filesystem_path(rpath) if self._fs_accessor else None
        )

    def __del__(self):
        try:
            self._ftp.close()
        except:
            pass


def register(registry):
    registry.add_hook("bd.storage.accessor.ftp", FTPAccessor)
