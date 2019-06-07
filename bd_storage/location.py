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

    def __init__(self, storage_name, accessor, schema, mask="*"):
        self._name = storage_name
        self._accessor = accessor
        self._schema = schema
        self._label_patterns = [x.strip() for x in mask.split()]

    @classmethod
    def create(cls, storage_type, storage_name, accessor, schema, mask='*'):
        if storage_type == 'local':
            return LocalStorage(storage_name, accessor, schema, mask)
        elif storage_type == 'remote':
            return RemoteStorage(storage_name, accessor, schema, mask)
        else:
            this._log.error('Unsupported storage type \'{}\''.format(storage_type))

    def name(self):
        return self._name

    def accessor(self):
        return self._accessor

    def schema(self):
        return self._schema

    def item(self, labels, fields):
        if not self.match(labels):
            return

        schema_item = self._schema.get_anchor_item(labels)
        if not schema_item:
            return

        uid = schema_item.resolve(fields)
        return StorageItem(labels, fields, uid, self)

    # def write_item(self, source_item, overwrite=False):
    #     source_storage = source_item.storage()
    #
    #     if source_storage is self:
    #         return source_item
    #
    #     labels, fields = source_item.labels(), source_item.fields()
    #
    #     if not self.match(source_item.labels()):
    #         return
    #
    #     target_schema_item = self._schema.get_anchor_item(labels)
    #     if not target_schema_item:
    #         return
    #
    #     uid = target_schema_item.resolve(fields)
    #
    #     target_item = StorageItem(labels, fields, uid, self)
    #
    #     if self._accessor.exists(uid) and not overwrite:
    #         return target_item
    #
    #     self._schema.build_structure(labels, fields)
    #
    #     return WriteIterator(self._accessor, uid)
    #
    # def remove_item(self, source_item):
    #     source_storage = source_item.storage()
    #
    #     if source_storage is self:
    #         return source_item
    #
    #     labels, fields = source_item.labels(), source_item.fields()
    #
    #     if not self.match(source_item.labels()):
    #         return
    #
    #     target_schema_item = self._schema.get_anchor_item(labels)
    #     if not target_schema_item:
    #         return
    #
    #     uid = target_schema_item.resolve(fields)
    #     if not self._accessor.exists(uid):
    #         return
    #
    #     self._accessor.rm(uid)
    #     self._accessor.rm(uid + '.meta')

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


class RemoteStorage(Storage):
    pass


class LocalStorage(Storage):

    def get_path(self, labels, fields):
        if not self.match(labels):
            return

        schema_item = self._schema.get_anchor_item(labels)
        if not schema_item:
            return

        uid = schema_item.resolve(fields)
        return self.accessor().resolve(uid)


class StorageItem(object):

    def __init__(self, labels, fields, uid, storage=None):
        self._labels = labels
        self._fields = fields
        self._uid = uid
        self._storage = storage

    def labels(self):
        return self._labels

    def fields(self):
        return self._fields

    def uid(self):
        return self._uid

    def storage(self):
        return self._storage

    def accessor(self):
        if not self._storage:
            return bd_hooks.execute(
                'storage.accessor.init.filesystem-accessor'
            ).one()
        return self._storage.accessor()

    def exists(self):
        return self.accessor().exists(self._uid)

    def open(self, mode):
        if 'w' in mode:
            self.storage().schema().build_structure(self._labels, self._fields)
        return self.accessor().open(self._uid, mode)

    def remove(self):
        self.accessor().rm(self._uid)

    def path(self):
        if self._storage is None:
            return self._uid

        if isinstance(self._storage, LocalStorage):
            return self._storage.get_path(self._labels, self._fields)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "StorageItem(labels={}, fields={}, uid={}, storage={})".format(
            repr(self._labels),
            repr(self._fields),
            self._uid,
            self._storage.name() if self._storage else None
        )


class DirectoryItem(StorageItem):
    pass


class FileItem(StorageItem):
    pass


class SequenceItem(StorageItem):
    pass


class StoragePool(object):

    def __init__(self, context):
        self._context = context
        self._storages = None
        self._load_storages()

    def _load_storages(self):
        if not self._storages:

            self._storages = OrderedDict()

            bd_hooks.load([os.path.join(os.path.dirname(bd_storage.__file__), 'hooks')])

            storage_configs = self._context.preset.config.get_value("storage")

            for storage_name, storage_config in storage_configs.items():

                accessor_name = storage_config["accessor"]["name"]
                accessor_kwargs = storage_config["accessor"].get("kwargs", {})

                try:
                    accessor = bd_hooks.execute(
                        "storage.accessor.init.{}".format(accessor_name),
                        **accessor_kwargs
                    ).one()
                except bd_hooks.exceptions.HookNotFoundError:
                    continue

                schema_name = storage_config["schema"]
                schema = Schema.new(self._context.preset.dir, schema_name, accessor)

                storage = Storage.create(
                    storage_config["type"],
                    storage_name,
                    accessor,
                    schema,
                    storage_config["mask"]
                )
                if storage:
                    self._storages[storage_name] = storage

        return self._storages.values()

    def _get_matching_storages(self, labels):
        storages = []
        for storage in self._load_storages():
            if storage.match(labels):
                storages.append(storage)
        return storages

    def paths(self, labels, fields={}):
        if 'project' not in fields:
            fields['project'] = self._context.project

        paths = []

        for storage in self._get_matching_storages(labels):
            item = storage.item(labels, fields)
            if item:
                path = item.path()
                if path:
                    paths.append(path)

        return paths

    def load_item(self, labels, fields={}, replicate=True):
        if 'project' not in fields:
            fields['project'] = self._context.project

        for storage in self._get_matching_storages(labels):

            item = storage.item(labels, fields)
            if not item.exists():
                continue

            if not replicate:
                return item

            return self.save_item(item)

    def save_item(self, item, overwrite=False, progress_callback=None):

        target_items = []
        target_descriptors = []

        for storage in self._get_matching_storages(item.labels()):

            target_item = storage.item(item.labels(), item.fields())
            if not target_item:
                continue

            target_items.append(target_item)
            if not target_item.exists() or overwrite:
                target_descriptors.append(target_item.open('wb+'))

        size = 0
        with item.open('rb') as src:

            while True:

                chunk = src.read(4096)
                if not chunk:
                    break

                size += len(chunk)

                if progress_callback is not None:
                    progress_callback(size)

                for target_descriptor in target_descriptors:
                    target_descriptor.write(chunk)

        for target_descriptor in target_descriptors:
            target_descriptor.close()

        return target_items[0]

    def init_item(self, labels, fields, path=None):
        if 'project' not in fields:
            fields['project'] = self._context.project

        return StorageItem(labels, fields, path)
