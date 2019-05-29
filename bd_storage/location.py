import os
import sys
import json
import logging
from fnmatch import fnmatch
from collections import OrderedDict

import six

import bd_hooks

import bd_storage
from .schema import Schema

this = sys.modules[__name__]
this._log = logging.getLogger(__name__.replace('bd_storage', 'bd'))


class Storage(object):

    def __init__(self, name, accessor, schema, mask="*", type="local"):
        self._name = name
        self._accessor = accessor
        self._schema = schema
        self._label_patterns = [x.strip() for x in mask.split()]
        self._type = type

    def get_name(self):
        return self._name

    def get_accessor(self):
        return self._accessor

    def get_schema(self):
        return self._schema

    def get_type(self):
        return self._type

    def get_item(self, labels, fields, check_exists=True):
        if not self.match(labels):
            return

        schema_item = self._schema.get_anchor_item(labels)
        if not schema_item:
            return

        uid = schema_item.resolve(fields)
        if not self._accessor.exists(uid) and check_exists:
            return

        return StorageItem(labels, fields, uid, self)

    def put_item(self, source_item, overwrite=False):
        source_storage = source_item.get_storage()

        if source_storage is self:
            return source_item

        labels, fields = source_item.get_labels(), source_item.get_fields()

        if not self.match(source_item.get_labels()):
            return

        target_schema_item = self._schema.get_anchor_item(labels)
        if not target_schema_item:
            return

        uid = target_schema_item.resolve(fields)

        target_item = StorageItem(labels, fields, uid, self)

        if self._accessor.exists(uid) and not overwrite:
            return target_item

        self._schema.build_structure(labels, fields)

        data = source_item.get_accessor().read(source_item.get_uid())

        self._accessor.write(uid, data)
        self._accessor.write(
            uid + '.meta',
            six.b(json.dumps({'labels': labels, 'fields': fields}, indent=2))
        )

        return target_item

    def remove_item(self, source_item):
        source_storage = source_item.get_storage()

        if source_storage is self:
            return source_item

        labels, fields = source_item.get_labels(), source_item.get_fields()

        if not self.match(source_item.get_labels()):
            return

        target_schema_item = self._schema.get_anchor_item(labels)
        if not target_schema_item:
            return

        uid = target_schema_item.resolve(fields)
        if not self._accessor.exists(uid):
            return

        self._accessor.rm(uid)
        self._accessor.rm(uid + '.meta')

    def match(self, labels):
        for label in labels:
            for pattern in self._label_patterns:

                if pattern == "*":
                    continue

                if pattern.startswith("^"):
                    pattern = pattern.lstrip('^')
                    match = not fnmatch(label, pattern)
                else:
                    match = fnmatch(label, pattern)

                if not match:
                    return False

        return True

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Storage(name={}, accessor={})".format(
            self._name,
            self._accessor
        )


class StorageItem(object):

    def __init__(self, labels, fields, uid, storage=None):
        self._labels = labels
        self._fields = fields
        self._uid = uid
        self._storage = storage

    def get_labels(self):
        return self._labels

    def get_fields(self):
        return self._fields

    def get_uid(self):
        return self._uid

    def get_storage(self):
        return self._storage

    def get_accessor(self):
        if not self._storage:
            return bd_hooks.execute(
                'storage.accessor.init.filesystem-accessor'
            ).one()
        return self._storage.get_accessor()

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "StorageItem(labels={}, fields={}, uid={}, storage={})".format(
            repr(self._labels),
            repr(self._fields),
            self._uid,
            self._storage.get_name() if self._storage else None
        )


class StoragePool(object):

    def __init__(self, context):
        self._context = context
        self._storages = None
        self._get_storages()

    def _get_storages(self):
        if not self._storages:

            self._storages = OrderedDict()

            bd_hooks.load([os.path.join(os.path.dirname(bd_storage.__file__), 'hooks')])

            cfg_storages = self._context.preset.config.get_value("storage")

            for name, cfg_storage in cfg_storages.items():

                try:
                    accessor = bd_hooks.execute(
                        "storage.accessor.init.{}".format(cfg_storage["accessor"]["name"]),
                        **cfg_storage["accessor"].get("kwargs", {})
                    ).one()
                except bd_hooks.exceptions.HookNotFoundError:
                    continue

                schema = Schema.new(self._context.preset.dir, cfg_storage["schema"], accessor)

                self._storages[name] = Storage(name,
                                               accessor,
                                               schema,
                                               cfg_storage["mask"],
                                               cfg_storage["type"])

        return self._storages.values()

    def _get_matching_storages(self, labels):
        for storage in self._get_storages():

            if not storage.match(labels):
                continue

            yield storage

    def get_item(self, labels, fields={}, replicate=False, check_exists=True):
        if 'project' not in fields:
            fields['project'] = self._context.project

        for storage in self._get_matching_storages(labels):

            item = storage.get_item(labels, fields, check_exists)
            if not item:
                continue

            if not replicate:
                return item

            return self.put_item(item)

    def put_item(self, source_item, overwrite=False):
        target_item = None

        for storage in reversed(list(self._get_matching_storages(source_item.get_labels()))):
            target_item = storage.put_item(source_item, overwrite) or target_item

        return target_item

    def new_item(self, labels, fields, path=None):
        if 'project' not in fields:
            fields['project'] = self._context.project

        return StorageItem(labels, fields, path, None)

    def remove_item(self, source_item):
        for storage in reversed(list(self._get_matching_storages(source_item.get_labels()))):
            storage.remove_item(source_item)
