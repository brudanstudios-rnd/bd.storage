import logging
from fnmatch import fnmatch
from collections import OrderedDict

from .. import config
from .. import hooks
from ..exceptions import *
from .accessor.filesystem import FileSystemAccessor
from .schema import Schema


LOGGER = logging.getLogger(__name__)


class AccessorRegistry(object):

    def __init__(self):
        self._structures = {}
        self._accessors = {}

    def add_accessor(self, name, accessor):
        self._accessors[name] = accessor

    def get_accessor(self, name):
        return self._accessors.get(name)


class Storage(object):

    def __init__(self, name, accessor, schema, mask="*", type="local"):
        self._name = name
        self._accessor = accessor
        self._schema = schema
        self._label_patterns = map(lambda x: x.strip(), mask.split())
        self._type = type

    def get_name(self):
        return self._name

    def get_accessor(self):
        return self._accessor

    def get_schema(self):
        return self._schema

    def get_type(self):
        return self._type

    def get_item(self, labels, context):
        if not self.match(labels):
            return

        schema_item = self._schema.get_anchor_item(labels)
        if not schema_item:
            return

        uid = schema_item.resolve(context)
        if not self._accessor.exists(uid):
            return

        return StorageItem(labels, context, uid, self)

    def put_item(self, source_item):
        source_storage = source_item.get_storage()

        if source_storage is self:
            return source_item

        labels, context = source_item.get_labels(), source_item.get_context()

        if not self.match(source_item.get_labels()):
            return

        target_schema_item = self._schema.get_anchor_item(labels)
        if not target_schema_item:
            return

        uid = target_schema_item.resolve(context)
        if self._accessor.exists(uid):
            return

        target_item = StorageItem(labels, context, uid, self)

        if self._accessor.exists(uid):
            return target_item

        self._schema.build_structure(labels, context)

        data = source_item.get_accessor().read(source_item.get_uid())
        self._accessor.write(uid, data)

        return target_item

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
        return "Storage(name={}, accessor={}, structure={})".format(
            self._name,
            self._accessor.name,
            self._structure.name
        )


class StorageItem(object):

    def __init__(self, labels, context, uid, storage=None):
        self._labels = labels
        self._context = context
        self._uid = uid
        self._storage = storage

    def get_labels(self):
        return self._labels

    def get_context(self):
        return self._context

    def get_uid(self):
        return self._uid

    def get_storage(self):
        return self._storage

    def get_accessor(self):
        if not self._storage:
            return FileSystemAccessor.new()
        return self._storage.get_accessor()

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "StorageItem(labels={}, context={}, uid={}, storage={})".format(
            repr(self._labels),
            repr(self._context),
            self._uid,
            self._storage.get_name()
        )


class StoragePool(object):

    def __init__(self):
        self._storages = None
        self._get_storages()

    def _get_storages(self):
        if not self._storages:

            self._storages = OrderedDict()

            registry = AccessorRegistry()

            registry.add_accessor(FileSystemAccessor.name, FileSystemAccessor)

            try:
                hooks.load_hooks()
            except Error as e:
                LOGGER.warning(str(e))
            else:
                hooks.execute("storage.register.structure", registry).all()
                hooks.execute("storage.register.accessor", registry).all()

            cfg_storages = config.get_value("storage")

            for name, cfg_storage in cfg_storages.iteritems():

                accessor_cls = registry.get_accessor(cfg_storage["accessor"]["name"])
                if not accessor_cls:
                    continue

                accessor = accessor_cls.new(**cfg_storage["accessor"].get("kwargs", {}))

                schema = Schema.new(cfg_storage["schema"], accessor)

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

    def get_item(self, labels, context, replicate=False):
        for storage in self._get_matching_storages(labels):

            item = storage.get_item(labels, context)
            if not item:
                continue

            if not replicate:
                return item

            return self.put_item(item)

    def put_item(self, source_item):
        target_item = None

        for storage in reversed(list(self._get_matching_storages(source_item.get_labels()))):
            target_item = storage.put_item(source_item) or target_item

        return target_item

    def new_item(self, labels, context, path=None):
        return StorageItem(labels, context, path, None)
