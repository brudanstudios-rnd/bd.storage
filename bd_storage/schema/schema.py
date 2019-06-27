__all__ = ["Schema"]

import os
import sys
import logging

import pathlib2

from .item import \
    SchemaItem, \
    SchemaDir, \
    SchemaAnchor, \
    SchemaFile


this = sys.modules[__name__]
this._log = logging.getLogger(__name__.replace('bd_storage', 'bd'))


class Schema(object):

    def __init__(self, schema_dir, accessor, formatter):
        self._schema_dir = schema_dir
        self._anchor_items = {}
        self._accessor = accessor
        self._formatter = formatter
        self._load()

    @classmethod
    def create(cls, preset_dir, schema_name, accessor, formatter):
        preset_dir = pathlib2.Path(preset_dir)

        schema_dir = preset_dir / "schemas" / schema_name

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

        for root, dirs, files in os.walk(str_schema_dir):

            root = pathlib2.Path(root)
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

                    labels = schema_anchor.config.get('labels')
                    if not labels:
                        continue

                    self._anchor_items[frozenset(labels)] = schema_anchor

                else:
                    SchemaFile.create(root / filename)

    def formatter(self):
        return self._formatter

    def get_anchor_item(self, labels):
        return self._anchor_items.get(frozenset(labels))

    def get_uid_from_data(self, labels, fields):
        item = self._anchor_items.get(frozenset(labels))
        if item:
            return self._formatter.format(item.template, **fields)

    def get_data_from_uid(self, uid, labels=None):
        if labels:
            schema_anchor = self._anchor_items.get(frozenset(labels))
            if not schema_anchor:
                return

            fields = self._formatter.parse(uid, schema_anchor.template)
            if fields:
                return fields
        else:
            for labels, schema_anchor in self._anchor_items.items():
                fields = self._formatter.parse(uid, schema_anchor.template)
                if fields:
                    return list(labels), fields

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

    def build_structure(self, labels, fields):
        schema_item = self._anchor_items.get(frozenset(labels))
        if schema_item:
            if not self._build_item(schema_item, fields):
                return False

        for schema_item in SchemaItem.items():

            if isinstance(schema_item, SchemaAnchor):
                continue

            if schema_item.is_triggered(labels, fields):
                if not self._build_item(schema_item, fields):
                    return False

        return True
