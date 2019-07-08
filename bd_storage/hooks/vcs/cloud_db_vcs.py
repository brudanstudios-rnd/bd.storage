import sys
import hashlib

import bd_rest_api

from bd_storage.abstract.vcs import VCS
from bd_storage.logger import get_logger

this = sys.modules[__name__]
this._log = get_logger(__name__)


class CloudDBVersionControl(VCS):

    def is_centralized(self):
        return True

    def _create_file_id(self, labels, fields):
        _fields = fields.copy()
        _fields.pop('version', None)
        return hashlib.sha1(
            str(
                tuple(sorted(labels))
            ) + str(
                tuple(sorted(_fields.items()))
            )
        ).hexdigest()

    def get_incremented_version(self, labels, fields, schema, accessor):
        result = bd_rest_api.File(self._create_file_id(labels, fields)).save()
        return result['version']

    def get_latest_version(self, labels, fields, schema, accessor):
        return bd_rest_api.File(self._create_file_id(labels, fields)).version


def register(registry):
    registry.add_hook('storage.vcs.init.cloud-db-vcs', CloudDBVersionControl)
