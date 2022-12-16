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
    def __init__(
        self, endpoint_url=None, bucket=None, access_key_id=None, secret_access_key=None
    ):
        super(S3Accessor, self).__init__()

        with warnings.catch_warnings(record=True):
            warnings.filterwarnings("ignore")

            self._s3 = boto3.resource(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                config=Config(signature_version="s3v4"),
            )

        self._bucket = self._s3.Bucket(bucket)

    def read(self, rpath):
        data_buffer = BytesIO()
        try:
            self._bucket.download_fileobj(rpath, data_buffer)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return

        return data_buffer.getvalue()

    def write(self, rpath, data):
        data_buffer = BytesIO(data)
        self._bucket.put_object(Key=rpath, Body=data_buffer)

    def list(self, rpath, relative=True, recursive=True):
        if not rpath.endswith("/"):
            rpath += "/"

        start_index = len(rpath)

        if not recursive:
            result = self._bucket.meta.client.list_objects_v2(
                Bucket=self._bucket.name, Delimiter="/", Prefix=rpath
            )

            contents = []
            for entry in result.get("CommonPrefixes", []):
                path = entry["Prefix"]
                contents.append(path[start_index:] if relative else path)

            for entry in result.get("Contents", []):
                path = entry["Key"]
                contents.append(path[start_index:] if relative else path)

            return contents
        else:
            return [
                obj.key[start_index:] if relative else obj.key
                for obj in self._bucket.objects.filter(Prefix=rpath)
            ]

    def make_dir(self, rpath, recursive=False):
        self._bucket.put_object(Key=rpath)

    def rm(self, rpath):
        if rpath.endswith("/"):
            self._bucket.objects.filter(Prefix=rpath).delete()

        self._bucket.Object(rpath).delete()

    def exists(self, rpath):
        try:
            self._bucket.Object(rpath).load()
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            else:
                raise
        else:
            return True

    def get_filesystem_path(self, rpath):
        return


def register(registry):
    registry.add_hook("bd.storage.accessor.s3", S3Accessor)
