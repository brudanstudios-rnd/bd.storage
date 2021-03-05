import sys
import uuid
import logging

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from bd.storage._vendor.six import BytesIO, reraise
from bd.storage.accessor import BaseAccessor
from bd.storage.utils import putils
from bd.storage.errors import *

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)


class S3Accessor(BaseAccessor):

    def __init__(self,
                 root=None, endpoint_url=None, bucket=None,
                 access_key_id=None, secret_access_key=None):
        super(S3Accessor, self).__init__(root)

        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._s3 = boto3.resource(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version='s3v4')
        )
        self._bucket = self._s3.Bucket(bucket)

    def resolve(self, uid):
        if not self._root:
            return uid
        return putils.join(self._root, uid)

    # def read(self, uid):
    #
    #     data_buffer = BytesIO()
    #
    #     try:
    #         self._ftp.retrbinary('RETR {}'.format(uid), data_buffer.write)
    #     except ftplib.error_perm as e:
    #
    #         # if file doesn't exist
    #         if e.message[:3] == '550':
    #             return
    #
    #         raise
    #
    #     return data_buffer.getvalue()
    #
    # def write(self, uid, data):
    #     self._ensure_connected()
    #
    #     transit_path = self._get_transit_path(uid)
    #
    #     data_buffer = BytesIO(data)
    #
    #     try:
    #         parent_dir = putils.dirname(uid)
    #         if not self.exists(parent_dir):
    #             self.make_dir(parent_dir, recursive=True)
    #
    #         # write to transit file
    #         self._ftp.storbinary('STOR {}'.format(transit_path), data_buffer)
    #
    #         # set permissions on transit file
    #         try:
    #             self._ftp.sendcmd('SITE CHMOD {} {}'.format(
    #                 str(self._write_mode), transit_path)
    #             )
    #         except ftplib.error_perm as e:
    #             # CHMODE command is not implemented
    #             # if the server is running on windows
    #             if e.message[:3] != '504':
    #                 raise
    #
    #         # rename transit path to the final path
    #         self._ftp.rename(transit_path, uid)
    #     finally:
    #         try:
    #             if self.exists(transit_path):
    #                 self._ftp.delete(transit_path)
    #         except:
    #             pass
    #
    # def _is_dir(self, uid):
    #     pwd = self._ftp.pwd()
    #     try:
    #         self._ftp.cwd(uid)
    #         return True
    #     except:
    #         return False
    #     finally:
    #         self._ftp.cwd(pwd)
    #
    # def _is_file(self, uid):
    #     if not self.exists(uid):
    #         return False
    #
    #     return not self._is_dir(uid)
    #
    # def _traverse(self):
    #     data = []
    #     current_dir = self._ftp.pwd()
    #     for entry in (path for path in self._ftp.nlst() if path not in ('.', '..')):
    #         try:
    #             self._ftp.cwd(entry)
    #         except ftplib.error_perm as e:
    #
    #             # we get here only if cwd command failed
    #             # it fails when the path is a file
    #             if e.message[:3] != '550':
    #                 raise
    #
    #             data.append(putils.join(current_dir, entry))
    #         else:
    #             data.extend(self._traverse())
    #             self._ftp.cwd('..')
    #
    #     return data

    def list(self, uid, relative=True, recursive=True):
        result = self._bucket.meta.client.list_objects(
            Bucket=self._bucket.name,
            Delimiter='/',
            Prefix=uid
        )
        return [obj.get('Prefix') for obj in result.get('CommonPrefixes')]

        # self._bucket.objects.filter(Prefix=uid, Delimiter='/')

        # initial_dir = uid.rstrip('/')
        #
        # self._ftp.cwd(initial_dir)
        #
        # try:
        #     if recursive:
        #         start_index = len(initial_dir)
        #         return [
        #             path[start_index + 1:] if relative else path
        #             for path in self._traverse()
        #             if path not in ['.', '..']
        #         ]
        #
        #     return [
        #         entry if relative else putils.join(initial_dir, entry)
        #         for entry in self._ftp.nlst()
        #         if entry not in ('.', '..')
        #     ]
        # finally:
        #     self._ftp.cwd('/')

    def make_dir(self, uid, recursive=False):
        self._bucket.put_object(Key=uid)

    def rm(self, uid):
        if uid.endswith(uid):
            self._bucket.objects.filter(Prefix=uid, Delimiter='/').delete()

        self._bucket.Object(uid).delete()

    def exists(self, uid):
        try:
            self._bucket.Object(uid).load()
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                raise
        else:
            return True

    def get_filesystem_path(self, uid):
        return


def register(registry):
    registry.add_hook('s3', S3Accessor)
