import warnings
import logging

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from six import BytesIO

from bd.storage.accessor import BaseAccessor

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)


class S3Accessor(BaseAccessor):

    def __init__(self,
                 endpoint_url=None, bucket=None,
                 access_key_id=None, secret_access_key=None):
        super(S3Accessor, self).__init__()

        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key

        with warnings.catch_warnings(record=True):
            warnings.filterwarnings('ignore')

            self._s3 = boto3.resource(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                config=Config(signature_version='s3v4')
            )

        self._bucket = self._s3.Bucket(bucket)

    def read(self, uid):
        data_buffer = BytesIO()
        try:
            self._bucket.download_fileobj(uid, data_buffer)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return

        return data_buffer.getvalue()

    def write(self, uid, data):
        data_buffer = BytesIO(data)
        self._bucket.put_object(Key=uid, Body=data_buffer)

    def list(self, uid, relative=True, recursive=True):
        if not uid.endswith('/'):
            uid += '/'

        start_index = len(uid)

        if not recursive:
            result = self._bucket.meta.client.list_objects_v2(
                Bucket=self._bucket.name,
                Delimiter='/',
                Prefix=uid
            )

            contents = []
            for entry in result.get('CommonPrefixes', []):
                path = entry['Prefix']
                contents.append(path[start_index:] if relative else path)

            for entry in result.get('Contents', []):
                path = entry['Key']
                contents.append(path[start_index:] if relative else path)

            return contents
        else:
            return [obj.key[start_index:] if relative else obj.key for obj in self._bucket.objects.filter(Prefix=uid)]

    def make_dir(self, uid, recursive=False):
        self._bucket.put_object(Key=uid)

    def rm(self, uid):
        if uid.endswith('/'):
            self._bucket.objects.filter(Prefix=uid).delete()

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
