__all__ = ["Schema"]

import os
import sys
import logging

try:
    import pathlib
except:
    from .._vendor import pathlib2 as pathlib

from .item import \
    SchemaItem, \
    SchemaDir, \
    SchemaAnchor, \
    SchemaFile

this = sys.modules[__name__]
this._log = logging.getLogger(__name__)


class Schema(object):

    _cached_anchor_items = {}

    def __init__(self, schema_dir, accessor, formatter):
        self._schema_dir = schema_dir
        self._accessor = accessor
        self._formatter = formatter

        self._anchor_items = {}

        self._load()

    @classmethod
    def create(cls, schema_dir, accessor, formatter):
        schema_dir = pathlib.Path(schema_dir)

        if not schema_dir.exists():
            this._log.error(
                "Schema directory '{}' doesn't exist".format(schema_dir)
            )
            return

        if accessor is None:
            this._log.error("Unspecified Accessor object")
            return

        return cls(schema_dir, accessor, formatter)

    def _load(self):
        
        str_schema_dir = str(self._schema_dir.resolve())

        if str_schema_dir in self._cached_anchor_items:
            self._anchor_items = self._cached_anchor_items[str_schema_dir]
            return

        for root, dirs, files in os.walk(str_schema_dir):

            root = pathlib.Path(root)
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

                    schema_anchor = SchemaAnchor.create(root / filename)

                    tags = schema_anchor.config.get('tags')
                    if not tags:
                        continue
                    
                    tags_set = frozenset(tags)
                    items = self._anchor_items.get(tags_set, [])

                    items.append(schema_anchor)
                    
                    self._anchor_items[tags_set] = items
                    
                else:
                    SchemaFile.create(root / filename)

        self._cached_anchor_items[str_schema_dir] = self._anchor_items

    def _get_anchor_item(self, tags, fields, storage_type):
        items = self._anchor_items.get(frozenset(tags))
        for item in items:
            if storage_type in item.config.get('storage_types', []):
                return item

    def get_uid_from_data(self, tags, fields, storage_type):
        item = self._get_anchor_item(tags, fields, storage_type)
        if item:
            return self._formatter.format(item.template, **fields)

    def get_data_from_uid(self, uid, storage_type):
        max_num_fields = -1
        last_tags = last_fields = None

        for tags, schema_anchors in self._anchor_items.items():
            
            for schema_anchor in schema_anchors:

                storage_types = schema_anchor.config.get('storage_types', [])
                if storage_type not in storage_types:
                    continue

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

    def _build_item(self, item, fields):

        try:
            target_path = self._formatter.format(item.template, **fields)
        except KeyError as e:
            this._log.error('Missing field \'{}\' in format \'{}\''.format(e, item.template))
            return False

        if self._accessor.exists(target_path):
            return True

        parent_item = item if isinstance(item, SchemaDir) else item.parent

        parent_items = []
        while parent_item is not None:
            parent_items.append(parent_item)
            parent_item = parent_item.parent

        for parent_item in reversed(parent_items):

            try:
                target_dir_path = self._formatter.format(parent_item.template, **fields)
            except KeyError as e:
                this._log.error('Missing field \'{}\' in format \'{}\''.format(e, parent_item.template))
                return False

            if not self._accessor.exists(target_dir_path):
                try:
                    self._accessor.make_dir(target_dir_path)
                except Exception as e:
                    this._log.exception('Unable to build directory \'{}\':'.format(target_dir_path))
                    return False

        if isinstance(item, SchemaFile):
            try:
                content = item.path.read_bytes()
                self._accessor.write(target_path, content)
            except Exception as e:
                this._log.exception('Unable to build an item {}:'.format(item))
                return False

        return True

    def build_structure(self, tags, fields, storage_type):
        schema_item = self._get_anchor_item(tags, fields, storage_type)
        if schema_item:
            if not self._build_item(schema_item, fields):
                return False

        for schema_item in SchemaItem.items():

            if isinstance(schema_item, SchemaAnchor):
                continue

            if schema_item.is_triggered(tags, fields, storage_type):
                if not self._build_item(schema_item, fields):
                    return False

        return True
