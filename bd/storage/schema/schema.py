__all__ = ["Schema"]

import os
import sys
import logging
import posixpath as pp

from .item import \
    SchemaDir, \
    SchemaAnchor

this = sys.modules[__name__]
this._log = logging.getLogger(__name__)


class Schema(object):

    _cached_anchor_items = {}

    @classmethod
    def create(cls, schema_dir, formatter):

        schema_dir = schema_dir.replace(os.sep, pp.sep)

        if not os.path.exists(schema_dir):
            this._log.error(
                "Schema directory '{}' doesn't exist".format(schema_dir)
            )
            return

        return cls(schema_dir, formatter)

    def __init__(self, schema_dir, formatter):
        self._schema_dir = schema_dir
        self._formatter = formatter

        self._anchor_items = {}

        self._load()

    def _load(self):

        if self._schema_dir in self._cached_anchor_items:
            self._anchor_items = self._cached_anchor_items[self._schema_dir]
            return

        for root, dirs, files in os.walk(self._schema_dir):

            root = root.replace(os.sep, pp.sep)

            if root == self._schema_dir:
                continue

            SchemaDir.create(root)

            for filename in files:

                if filename.endswith('.yml'):

                    # skip .yml files which names match
                    # any directory name on the same level
                    if filename[:-4] in dirs:
                        continue

                    if not filename.startswith('anchor__'):
                        continue

                    schema_anchor = SchemaAnchor.create(pp.join(root, filename))

                    tags = schema_anchor.get_config('tags')
                    if not tags:
                        continue

                    self._anchor_items[frozenset(tags)] = schema_anchor

        self._cached_anchor_items[self._schema_dir] = self._anchor_items

    def _get_anchor_item(self, tags):
        return self._anchor_items.get(frozenset(tags))

    def get_uid_from_data(self, tags, fields):
        item = self._get_anchor_item(tags)
        if item:
            return self._formatter.format(item.template, **fields)

    def get_data_from_uid(self, uid):
        max_num_fields = -1
        last_tags = last_fields = None

        for tags, schema_anchor in self._anchor_items.items():

            fields = self._formatter.parse(uid, schema_anchor.template)
            if not fields:
                continue

            num_fields = len(fields)

            if num_fields > max_num_fields:

                last_tags = tags
                last_fields = fields

                max_num_fields = num_fields

        if last_fields:
            return list(last_tags), last_fields
