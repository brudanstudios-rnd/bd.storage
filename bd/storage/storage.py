__all__ = ['StoragePool']

import os
import sys
import uuid
import logging
import tempfile
import getpass
import json
import datetime

import bd.hooks as bd_hooks
# import bd.context as bd_context

from .accessor import FileSystemAccessor
from .formatter import FieldFormatter
from .schema import Schema
from . import utils

this = sys.modules[__name__]
this._log = logging.getLogger(__name__)


def _json_encoder(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.strftime("%m/%d/%Y %H:%M:%S")
    raise TypeError("Type {} not serializable".format(type(obj)))


class TraverseDirection:
    DOWNSTREAM, UPSTREAM = range(2)


class Storage(object):

    def __init__(self, name, accessor, schema, tag_mask=None):
        self.name = name
        self.accessor = accessor
        self.schema = schema
        self._tag_mask = utils.parse_mask(tag_mask) if tag_mask else None

    @classmethod
    def create_storage(cls, storage_name, storage_config):
        """Create storage object from provided configuration.

        Args:
            storage_name (str): storage name.
            storage_config (dict): storage configuration.

        Returns:
            Storage: fully setup storage object.

        """
        accessor = cls._create_accessor(storage_config["accessor"])
        schema = cls._create_schema(storage_config["schema"])

        return Storage(
            storage_name,
            accessor,
            schema,
            storage_config.get("tag_mask")
        )

    @classmethod
    def _create_accessor(cls, accessor_config):
        accessor_name = accessor_config.get("name", "fs")
        accessor_kwargs = accessor_config.get("kwargs", {})
        
        if accessor_name == 'fs':
            return FileSystemAccessor(**accessor_kwargs)

        return bd_hooks.execute(accessor_name, **accessor_kwargs).one()

    @classmethod
    def _create_schema(cls, schema_config):
        """Create storage schema from provided configuration.

        Args:
            accessor (Accessor): storage accessor object.   
            schema_config (dict): schema configuration.

        Returns:
            Schema: storage schema object.

        """
        dirname = schema_config['dir']
        fields_config = schema_config['fields']
        return Schema.create(
            dirname,
            FieldFormatter(fields_config)
        )

    def get_item(self, tags, fields):
        if not self.is_matching(tags):
            return

        uid = self.schema.get_uid_from_data(tags, fields)
        if not uid:
            return

        return StorageItem(
            tags,
            fields,
            uid=uid,
            storage=self
        )

    def get_item_from_filename(self, filename):
        uid = self.accessor.convert_filename_to_uid(filename)
        if not uid:
            return

        result = self.schema.get_data_from_uid(uid)
        if not result:
            return

        tags, fields = result

        if not self.is_matching(tags):
            return

        return StorageItem(
            tags,
            fields,
            uid=uid,
            storage=self
        )

    def is_matching(self, tags):
        if not self._tag_mask:
            return True

        return utils.match_tags(self._tag_mask, tags)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Storage(name='{}', accessor={})".format(
            self.name,
            self.accessor
        )


class BaseItem(object):

    def __init__(self, tags, fields):
        self.tags = tags[:]
        self.fields = fields.copy()
        self._userdata = None

    @property
    def common_tags(self):
        return [tag for tag in self.tags if not tag.startswith('_')]

    @property
    def extra_tags(self):
        return [tag for tag in self.tags if tag.startswith('_')]

    @property
    def common_fields(self):
        return {name: value for name, value in self.fields.items() if not name.startswith('_')}

    @property
    def extra_fields(self):
        return {name: value for name, value in self.fields.items() if name.startswith('_')}

    def add_tag(self, tag):
        if tag not in self.tags:
            self.tags.append(tag)
        return self

    def add_tags(self, *tags):
        for tag in tags:
            self.add_tag(tag)
        return self

    def remove_tag(self, tag):
        try:
            self.tags.remove(tag)
        except ValueError:
            pass
        return self

    def remove_tags(self, *tags):
        for tag in tags:
            self.remove_tag(tag)
        return self

    def replace_tag(self, old_tag, new_tag):
        return self.remove_tag(old_tag).add_tag(new_tag)

    def replace_tags(self, **kwargs):
        for old_tag, new_tag in kwargs.items():
            self.replace_tag(old_tag, new_tag)
        return self

    def set_field(self, name, value):
        self.fields[name] = value
        return self

    def set_fields(self, fields):
        self.fields.update(fields)

    def pop_field(self, name):
        return self.fields.pop(name, None)

    def pop_fields(self, names):
        popped_fields = {}
        for name in names:
            value = self.fields.pop(name, None)
            if value:
                popped_fields[name] = value
        return popped_fields

    def get_userdata(self, key):
        if self._userdata:
            return self._userdata.get(key)

    def set_userdata(self, key, value):
        if not self._userdata:
            self._userdata = {key: value}
        else:
            self._userdata[key] = value

    def get_userdata_dict(self):
        return self._userdata

    def set_userdata_dict(self, data):
        self._userdata = data


class MetaItem(BaseItem):

    def __init__(self,
                 tags,
                 fields,
                 filename=None):
        
        super(MetaItem, self).__init__(
            utils.remove_extra_tags(tags),
            utils.remove_extra_fields(fields)
        )

        self._is_temp = filename is None

        if self._is_temp:
            self._filename = os.path.join(
                tempfile.gettempdir(), 
                uuid.uuid4().hex
            )
        else:
            self._filename = filename

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, filename):
        self._is_temp = False
        self._filename = filename

    @property
    def exists(self):
        return os.path.exists(self._filename)

    def read(self):
        if not os.path.exists(self._filename):
            return

        with open(self._filename, 'rb') as f:
            return f.read()

    def write(self, data):
        with open(self._filename, 'wb') as f:
            f.write(data)

    def __del__(self):
        try:
            if self._is_temp and os.path.exists(self._filename):
                os.unlink(self._filename)
        except:
            this._log.exception(
                'Unable to delete temporary file \'{}\''.format(self._filename)
            )

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (
            "MetaItem(tags={}, fields={}, filename='{}')"
        ).format(
            repr(self.tags),
            repr(self.fields),
            self._filename
        )


class StorageItem(BaseItem):

    def __init__(self, tags, fields, uid, storage):
        super(StorageItem, self).__init__(tags, fields)
        self.uid = uid
        self.storage = storage
        self.accessor = self.storage.accessor
        self.next_item = None
        self.prev_item = None

    @property
    def exists(self):
        return self.accessor.exists(self.uid)

    @property
    def filename(self):
        return self.accessor.get_filename(self.uid)

    def read(self, direction=TraverseDirection.UPSTREAM):

        def _read_self():
            data = self.accessor.read(self.uid)
            if data is not None:
                this._log.debug('Read item data from storage "{}"'.format(self.storage.name))
                return data

        def _read_next():
            if self.next_item:
                return self.next_item.read(direction)

        if direction == TraverseDirection.UPSTREAM:
            data = _read_self()
            if data is not None:
                return data

            return _read_next()
        else:
            data = _read_next()
            if data is not None:
                return data

            return _read_self()

    def write(self, data, overwrite=False, direction=TraverseDirection.UPSTREAM):
        if not overwrite and self.exists:
            return

        def _write_self():
            this._log.debug('Writing item data to storage "{}"...'.format(self.storage.name))

            self.accessor.write(self.uid, data)

            if self._userdata:
                userdata = utils.remove_extra_fields(self._userdata)
                if userdata:
                    aux_data = {
                        'date': datetime.datetime.now(),
                        'user': getpass.getuser(),
                        'tags': self.tags,
                        'fields': self.fields
                    }
                    userdata.update(aux_data)

                    self.accessor.write(
                        self.uid + '.meta',
                        json.dumps(userdata, indent=2, default=_json_encoder)
                    )

            this._log.debug('Done')

        def _write_next():
            if self.next_item:

                if self._userdata:
                    self.next_item.set_userdata_dict(self._userdata)

                self.next_item.write(data, overwrite, direction)

        if direction == TraverseDirection.UPSTREAM:
            _write_self()
            _write_next()
        else:
            _write_next()
            _write_self()

    def make_directories(self):
        self.accessor.make_dir(self.uid, True)

    def remove(self, recursive=True):
        self.accessor.rm(self.uid)
        if recursive and self.next_item:
            self.next_item.remove(recursive)

    def replicate(self, overwrite=False, direction=TraverseDirection.DOWNSTREAM):
        data = self.read(direction)
        if data is not None:
            self.write(data, overwrite)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (
            "StorageItem(tags={}, fields={}, "
            "uid='{}', storage='{}')"
        ).format(
            repr(self.tags),
            repr(self.fields),
            self.uid,
            self.storage.name if self.storage else None
        )


class StoragePool(object):

    def __init__(self, storage_pool_config):
        self._pool_config = storage_pool_config

        self._storages = None

        self._get_storages()

    def _get_storages(self):
        """Initialize storages from provided configuration.

        Returns:
            list: Cached list of Storage objects.

        """
        if not self._storages:

            self._storages = []

            self._load_hooks()

            for storage_name, storage_config in self._pool_config.items():

                try:
                    storage = Storage.create_storage(
                        storage_name, storage_config)
                except Exception as e:
                    this._log.error(
                        'Failed to create storage "{}". {}'.format(storage_name, str(e)))
                    continue

                self._storages.append(storage)

        return self._storages

    def _load_hooks(self):
        """Load hooks stored under current package."""
        bd_hooks.load([os.path.join(os.path.dirname(__file__), 'hooks')])

    def _get_matching_storages(self, tags, stop_before=None):
        """Get a list of storages suitable to store items with specified tags.

        Args:
            tags (list[str]): a list of tags.
            stop_before (str, optional): stop iterating when the next 
                candidate storage has this name. Defaults to None.

        Returns:
            list[Storage]: a list of storages which mask matches provided tags.

        """
        storages = []
        for storage in self._get_storages():

            if stop_before and storage.name == stop_before:
                break

            if storage.is_matching(tags):
                storages.append(storage)

        return storages

    def get_item_from_filename(self, filename):
        for storage in self._storages:
            item = storage.get_item_from_filename(filename)
            if item:
                return self.get_item(item.tags, item.fields)

    def get_item(self, tags, fields):
        last_item = None
        current_item = None

        storages = self._get_matching_storages(tags)
        if not storages:
            this._log.error('Storage matching {} tags not found'.format(tags))
            return

        for storage in reversed(storages):

            item = storage.get_item(tags, fields)
            if not item:
                this._log.warning(
                    'There is no item in the storage "{}" matching the specified '
                    'combination of tags and fields: tags={}, fields={}'.format(storage.name, tags, fields)
                )
                continue

            current_item = item

            if last_item:
                current_item.next_item = last_item
                last_item.prev_item = current_item

            last_item = current_item

        return current_item
