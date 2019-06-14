import os
import sys
import logging
import hashlib
from fnmatch import fnmatch
from collections import OrderedDict

import bd_hooks
import bd.context
import bd_storage
from .schema import Schema

this = sys.modules[__name__]
this._log = logging.getLogger(__name__.replace('bd_storage', 'bd'))


class Storage(object):

    def __init__(self, storage_name, accessor, vcs, schema, mask="*"):
        self._name = storage_name
        self._accessor = accessor
        self._vcs = vcs
        self._schema = schema
        self._label_patterns = [x.strip() for x in mask.split()]

    @classmethod
    def create(cls, storage_type, storage_name, accessor, vcs, schema, mask='*'):
        if storage_type == 'local':
            return LocalStorage(storage_name, accessor, vcs, schema, mask)
        elif storage_type == 'remote':
            return RemoteStorage(storage_name, accessor, vcs, schema, mask)
        else:
            this._log.error('Unsupported storage type \'{}\''.format(storage_type))

    def name(self):
        return self._name

    def accessor(self):
        return self._accessor

    def vcs(self):
        return self._vcs

    def schema(self):
        return self._schema

    def get_anchor_item(self, labels, fields):
        if not self.is_matching(labels):
            return

        schema_item = self._schema.get_anchor_item(labels)
        if not schema_item:
            return

        uid = schema_item.resolve(fields)

        return StorageAnchorItem(labels, fields, uid, self)

    def is_matching(self, labels):
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
    pass


class StorageBasicItem(object):

    def __init__(self, uid, storage=None, parent=None):
        self._uid = uid
        self._storage = storage
        self._parent = parent
        self._accessor = None

    def uid(self, relative=False):
        if not relative and self._parent:
            return self.accessor().join(self._parent.uid(), self._uid)
        return self._uid

    def storage(self):
        return self._storage

    def accessor(self):
        if self._accessor is None:
            if self._storage is not None:
                self._accessor = self._storage.accessor()
            else:
                self._accessor = bd_hooks.execute(
                    'storage.accessor.init.filesystem-accessor'
                ).one()
        return self._accessor

    def exists(self):
        return self.accessor().exists(self.uid())

    def is_dir(self):
        return self.accessor().is_dir(self.uid())

    def is_file(self):
        return self.accessor().is_file(self.uid())

    def remove(self):
        self.accessor().rm(self.uid())

    def filesystem_path(self):
        if self._storage is None:
            return self._uid

        if isinstance(self._storage, LocalStorage):
            return self.accessor().resolve(self.uid())

    def read(self):
        return self.accessor().read(self.uid())

    def write(self, data):
        self.accessor().write(self.uid(), data)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "StorageItem(uid={}, storage={})".format(
            self.uid(relative=False),
            self._storage.name() if self._storage else None
        )


class StorageAnchorItem(StorageBasicItem):

    def __init__(self, labels, fields, uid, storage=None):
        super(StorageAnchorItem, self).__init__(uid, storage)
        self._labels = labels
        self._fields = fields
        self._items = None

    def labels(self):
        return self._labels

    def fields(self):
        return self._fields

    def add_item(self, item):
        item = StorageBasicItem(
            item.uid(relative=True), storage=self._storage, parent=self
        )
        self._items = self._items or []
        self._items.append(item)
        return item

    def items(self):
        if self._items is None:
            self._items = []
            for uid in self.accessor().list(self.uid(), relative=True):
                item = StorageBasicItem(uid, storage=self._storage, parent=self)
                self._items.append(item)

        return self._items

    def build_structure(self):
        self.storage().schema().build_structure(self._labels, self._fields)

    def __repr__(self):
        return "StorageAnchorItem(labels={}, fields={}, uid={}, storage={})".format(
            repr(self._labels),
            repr(self._fields),
            self.uid(),
            self._storage.name() if self._storage else None
        )


class StoragePool(object):

    def __init__(self, name, context=None):
        self._name = name
        self._context = context or bd.context.load()
        self._storages = None
        self._load_storages()

    def _load_storages(self):
        if not self._storages:

            self._storages = OrderedDict()

            bd_hooks.load([os.path.join(os.path.dirname(bd_storage.__file__), 'hooks')])

            storage_pool_configs = self._context.preset.config.get_value('storage_pools')
            if self._name not in storage_pool_configs:
                raise Exception('Storage pool with name \'{}\' not found'.format(self._name))

            storage_configs = self._context.preset.config.get_value('storages')

            for storage_name in storage_pool_configs[self._name]['storages']:

                if storage_name not in storage_configs:
                    raise Exception('Storage with name \'{}\' not found'.format(storage_name))

                storage_config = storage_configs[storage_name]

                accessor_name = storage_config["accessor"]["name"]
                accessor_kwargs = storage_config["accessor"].get("kwargs", {})

                try:
                    accessor = bd_hooks.execute(
                        "storage.accessor.init.{}".format(accessor_name),
                        **accessor_kwargs
                    ).one()
                except bd_hooks.exceptions.HookNotFoundError:
                    continue

                vcs_name = storage_config["vcs"]["name"]
                vcs_kwargs = storage_config["vcs"].get("kwargs", {})

                try:
                    vcs = bd_hooks.execute(
                        "storage.vcs.init.{}".format(vcs_name),
                        **vcs_kwargs
                    ).one()
                except bd_hooks.exceptions.HookNotFoundError:
                    continue

                schema_name = storage_config["schema"]
                schema = Schema.new(self._context.preset.dir, schema_name, accessor)

                storage = Storage.create(
                    storage_config["type"],
                    storage_name,
                    accessor,
                    vcs,
                    schema,
                    storage_config["mask"]
                )
                if storage:
                    self._storages[storage_name] = storage

        return self._storages.values()

    def _get_matching_storages(self, labels):
        storages = []
        for storage in self._load_storages():
            if storage.is_matching(labels):
                storages.append(storage)
        return storages

    def get_filesystem_paths(self, labels, fields={}):
        if 'project' not in fields:
            fields['project'] = self._context.project

        paths = []

        for storage in self._get_matching_storages(labels):
            item = storage.get_anchor_item(labels, fields)
            if item:
                path = item.filesystem_path()
                if path:
                    paths.append(path)

        return paths

    def load_item(self, labels, fields={}, replicate=True, progress_callback=None):
        if 'project' not in fields:
            fields['project'] = self._context.project

        checked_versions = {}
        for storage in self._get_matching_storages(labels):

            current_fields = fields.copy()

            if 'version' not in fields:
                vcs = storage.vcs()
                vcs_name = vcs.__class__.__name__
                if vcs_name in checked_versions:
                    version = checked_versions[vcs_name]
                else:
                    version = vcs.get_latest_version(labels, fields)
                    checked_versions[vcs_name] = version

                current_fields['version'] = version

            item = storage.get_anchor_item(labels, current_fields)
            if not item:
                continue

            if not item.exists():
                continue

            if not replicate:
                return item

            return self.save_item(item, progress_callback=progress_callback)

    def save_item(self, src_anchor_item, overwrite=False, progress_callback=None):

        labels, fields = src_anchor_item.labels(), src_anchor_item.fields()

        fields.pop('version', None)

        read_items = src_anchor_item.items()
        if not read_items:
            read_items = [src_anchor_item]

        return_item = None

        per_storage_write_items = []

        checked_versions = {}

        for storage in self._get_matching_storages(labels):

            vcs = storage.vcs()
            vcs_name = vcs.__class__.__name__
            if vcs_name in checked_versions:
                version = checked_versions[vcs_name]
            else:
                version = vcs.get_incremented_version(labels, fields)
                checked_versions[vcs_name] = version

            current_fields = fields.copy()
            current_fields['version'] = version

            dest_anchor_item = storage.get_anchor_item(labels, current_fields)
            if not dest_anchor_item:
                continue

            if return_item is None:
                return_item = dest_anchor_item

            if dest_anchor_item.exists() and not overwrite:
                continue

            write_items = []
            for src_nested_item in src_anchor_item.items():
                write_items.append(dest_anchor_item.add_item(src_nested_item))

            if not write_items:
                write_items = [dest_anchor_item]

            dest_anchor_item.build_structure()

            per_storage_write_items.append(write_items)

        num_read_items = len(read_items)
        num_items = num_read_items + len(per_storage_write_items) * num_read_items

        num_processed_items = 0

        for i, read_item in enumerate(read_items):

            data = read_item.read()
            num_processed_items += 1

            for write_items in per_storage_write_items:

                write_item = write_items[i]

                if progress_callback is not None:
                    progress = int(100 * num_processed_items / float(num_items))
                    progress_callback(progress, read_item, write_item)

                write_item.write(data)
                num_processed_items += 1

                if progress_callback is not None:
                    progress = int(100 * num_processed_items / float(num_items))
                    progress_callback(progress, read_item, write_item)

        return return_item

    def create_item(self, labels, fields, path=None):
        if 'project' not in fields:
            fields['project'] = self._context.project

        return StorageAnchorItem(labels, fields, path)
