import sys
import hashlib
import logging

import bd_rest_api

this = sys.modules[__name__]
this._log = logging.getLogger(__name__.replace('bd_storage', 'bd'))


class CloudDBVersionControl(object):

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
