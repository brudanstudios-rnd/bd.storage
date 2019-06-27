import os
import sys
import uuid
import logging
import tempfile
from fnmatch import fnmatch

import bd_hooks
import bd.context

import bd_storage

from .formatter import StringFormatter
from .schema import Schema

this = sys.modules[__name__]
this._log = logging.getLogger(__name__.replace('bd_storage', 'bd'))


class Storage(object):

    def __init__(self, storage_name, accessor, vcs, schema, mask="*", is_remote=False):
        self._name = storage_name
        self._accessor = accessor
        self._vcs = vcs
        self._schema = schema
        self._label_patterns = [x.strip() for x in mask.split()]
        self._is_remote = is_remote

    def name(self):
        return self._name

    def accessor(self):
        return self._accessor

    def vcs(self):
        return self._vcs

    def schema(self):
        return self._schema

    def is_remote(self):
        return self._is_remote

    def make_anchor_item(self, labels, fields):
        if not self.is_matching(labels):
            return

        uid = self._schema.get_uid_from_data(labels, fields)
        if not uid:
            return

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

    def filesystem_path(self):
        if self._storage is None:
            return self._uid

        if not self._storage.is_remote():
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

    def __init__(self, labels, fields, uid=None, storage=None):

        self._is_transient = storage is None and uid is None
        if self._is_transient:
            uid = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)

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

    def __del__(self):
        if self._is_transient:
            try:
                self.accessor().rm(self.uid())
            except:
                this._log.exception(
                    'Unable to delete temporary file \'{}\''.format(self.uid())
                )

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

            self._storages = []

            bd_hooks.load([os.path.join(os.path.dirname(bd_storage.__file__), 'hooks')])

            storage_pool_configs = self._context.preset.config.get_value('storage_pools')
            if self._name not in storage_pool_configs:
                raise Exception('Storage pool with name \'{}\' not found'.format(self._name))

            storage_configs = self._context.preset.config.get_value('storages')
            field_configs = self._context.preset.config.get_value('fields')

            for storage_name in storage_pool_configs[self._name]:

                if storage_name not in storage_configs:
                    raise Exception('Storage with name \'{}\' not found'.format(storage_name))

                storage_config = storage_configs[storage_name]

                accessor_name = storage_config["accessor"]["name"]

                try:
                    accessor = bd_hooks.execute(
                        "storage.accessor.init.{}".format(accessor_name),
                        storage_config["accessor"]['root']
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

                schema_name = storage_config["schema"]['name']
                field_config_name = storage_config["schema"]['fields']

                if field_config_name not in field_configs:
                    raise Exception(
                        'Field configuration with name \'{}\' not found'.format(field_config_name)
                    )

                formatter = StringFormatter(field_configs[field_config_name])

                schema = Schema.create(
                    self._context.preset.dir, schema_name, accessor, formatter
                )

                storage = Storage(
                    storage_name,
                    accessor,
                    vcs,
                    schema,
                    storage_config["mask"],
                    storage_config.get('is_remote', False)
                )

                self._storages.append(storage)

        return self._storages

    def _get_matching_storages(self, labels):
        storages = []
        for storage in self._load_storages():
            if storage.is_matching(labels):
                storages.append(storage)
        return storages

    def get_filesystem_paths(self, labels, fields={}):
        fields = self._update_fields(fields)

        paths = []

        for storage in self._get_matching_storages(labels):

            item = storage.make_anchor_item(labels, fields)
            if not item:
                continue

            path = item.filesystem_path()
            if path:
                paths.append(path)

        return paths

    def build_structure(self, labels, fields={}):
        fields = self._update_fields(fields)

        for storage in self._get_matching_storages(labels):
            storage.schema().build_structure(labels, fields)

    def load_item_by_path(self, path, replicate=True):
        try:
            uid = path[path.index(self._context.project):]
        except ValueError:
            this._log.error(
                'Project name \'{}\' not found in path: {}'.format(self._context.project, path)
            )
            return

        for storage in self._storages:
            result = storage.schema().get_data_from_uid(uid)
            if not result:
                continue

            return self.load_item(*result, replicate=replicate)

    def load_item(self, labels, fields={}, replicate=True, ignore_version_field=False):
        fields = self._update_fields(fields, ignore_version_field)

        checked_versions = {}

        for storage in self._get_matching_storages(labels):

            version = fields.get('version')
            if not version:
                vcs = storage.vcs()
                vcs_name = vcs.__class__.__name__
                if vcs.is_centralized() and vcs_name in checked_versions:
                    version = checked_versions[vcs_name]
                else:
                    version = vcs.get_latest_version(labels, fields, storage.schema(), storage.accessor())

                    # means that this storage doesn't have the item on it
                    if version is None:
                        continue

                    checked_versions[vcs_name] = version

            _fields = fields.copy()
            _fields['version'] = version

            item = storage.make_anchor_item(labels, _fields)
            if not item:
                continue

            # if a specific version of the item was
            # requested by the user and it doesn't exist,
            # continue looking for it on other storages
            if 'version' in fields and not item.exists():
                continue

            # without replication an item on the remote storage
            # could be returned, which blocks the user from getting
            # a filesystem path of that item
            if not replicate:
                return item

            return self.save_item(item, stop_on_storage=storage.name())

    def save_item(self, item, overwrite=False, ignore_version_field=False, stop_on_storage=None):

        labels = item.labels()
        fields = self._update_fields(item.fields(), ignore_version_field)

        read_items = item.items()
        if not read_items:
            read_items = [item]

        return_item = None

        per_storage_write_items = []

        checked_versions = {}

        for storage in self._get_matching_storages(labels):

            if stop_on_storage is not None and storage.name() == stop_on_storage:
                break

            version = fields.get('version')
            if not version:
                vcs = storage.vcs()
                vcs_name = vcs.__class__.__name__
                if vcs.is_centralized() and vcs_name in checked_versions:
                    version = checked_versions[vcs_name]
                else:
                    version = vcs.get_incremented_version(labels, fields, storage.schema(), storage.accessor())
                    checked_versions[vcs_name] = version

            _fields = fields.copy()
            _fields['version'] = version

            dest_anchor_item = storage.make_anchor_item(labels, _fields)
            if not dest_anchor_item:
                continue

            if return_item is None:
                return_item = dest_anchor_item

            if dest_anchor_item.exists() and not overwrite:
                continue

            write_items = []
            for src_nested_item in item.items():
                write_items.append(dest_anchor_item.add_item(src_nested_item))

            if not write_items:
                write_items = [dest_anchor_item]

            dest_anchor_item.build_structure()

            per_storage_write_items.append(write_items)

        for i, read_item in enumerate(read_items):

            data = read_item.read()

            for write_items in per_storage_write_items:
                write_items[i].write(data)

        return return_item or item

    def make_item(self, labels, fields, path=None, storage=None):
        fields = self._update_fields(fields, True)
        return StorageAnchorItem(labels, fields, path, storage)

    def _update_fields(self, fields, strip_version=False):
        fields = fields.copy()

        if 'project' not in fields:
            fields['project'] = self._context.project

        if 'user' not in fields:
            fields['user'] = os.environ['BD_USER']

        if 'version' in fields and strip_version:
            fields.pop('version', None)

        return fields
