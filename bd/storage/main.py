__all__ = ['StorageManager']

import os
import sys
import uuid
import logging
import tempfile
import getpass
import json
import datetime
from fnmatch import fnmatch

import bd.hooks as bd_hooks
import bd.context as bd_context

from .component import Component
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


class OperationMode:
    LOAD, SAVE = range(2)


class StorageType:
    PUBLISH, CHECKOUT, REMOTE = ('publish', 'checkout', 'remote')


class Storage(object):

    def __init__(self, name, accessor, schema, storage_type=StorageType.CHECKOUT, tag_mask=None):
        self.name = name
        self.accessor = accessor
        self.schema = schema
        self.type = storage_type
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

        schema = cls._create_schema(
            accessor,
            storage_config["schema"]
        )
        return Storage(
            storage_name,
            accessor,
            schema,
            storage_config.get("type", StorageType.CHECKOUT),
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
    def _create_schema(cls, accessor, schema_config):
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
            accessor,
            FieldFormatter(fields_config)
        )

    def get_item(self, tags, fields):
        if not self.is_matching(tags):
            return

        uid = self.schema.get_uid_from_data(tags, fields, self.type)
        if not uid:
            return

        return StorageItem(
            tags,
            fields,
            uid=uid,
            storage=self
        )

    def get_item_by_filename(self, filename):
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

    def build_structure(self, tags, fields):
        self.schema.build_structure(tags, fields, self.type)

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
        self.is_sequence = '__index__' in fields
        self.component = None
        self._userdata = None

    def add_tag(self, tag):
        if tag not in self.tags:
            self.tags.append(tag)
        return self

    def remove_tag(self, tag):
        try:
            self.tags.remove(tag)
        except ValueError:
            pass
        return self

    def replace_tag(self, old_tag, new_tag):
        self.remove_tag(old_tag).add_tag(new_tag)

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

    @classmethod
    def from_component(cls, component, as_revision=True, published_only=False):
        meta_item = cls(
            component.tags, 
            component.fields
        )

        meta_item.fields.update(component.get_version_data(as_revision, published_only))
        meta_item.component = component

        if not as_revision:
            meta_item.add_tag('__release__')

        return meta_item

    def __init__(self,
                 tags,
                 fields,
                 filename=None):
        
        super(MetaItem, self).__init__(tags, fields)
        
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
        self.filename = self.accessor.get_filename(self.uid)
        self.exists = self.accessor.exists(self.uid)

    def read(self, index=None):
        if index is not None:

            self.fields['__index__'] = index

            item = self.storage.get_item(self.tags, self.fields)
            if item:
                return item.read()

        else:
            return self.accessor.read(self.uid)

    def write(self, data, index=None):
        if index is not None:

            self.fields['__index__'] = index

            item = self.storage.get_item(self.tags, self.fields)
            if item:
                item.write(data)

        else:
            self.accessor.write(self.uid, data)

            if not self._userdata:
                return

            aux_data = {
                'date': datetime.datetime.now(),
                'user': getpass.getuser()
            }
            self._userdata.update(aux_data)

            self.accessor.write(
                self.uid + '.meta',
                json.dumps(self._userdata, indent=2, default=_json_encoder)
            )

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


class StorageManager(object):

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
                    print(type(e))
                    this._log.error(
                        'Failed to create storage "{0}". {1}'.format(storage_name, str(e)))
                    continue

                self._storages.append(storage)

        return self._storages

    def _load_hooks(self):
        """Load hooks stored under current package."""
        bd_hooks.load([os.path.join(os.path.dirname(__file__), 'hooks')])

    def _get_matching_storages(self, tags, storage_type=StorageType.CHECKOUT, stop_before=None):
        """Get a list of storages suitable to store items with specified tags.

        Args:
            tags (list[str]): a list of tags.
            storage_type (StorageType, optional): type of storage to consider.
            stop_before (str, optional): stop iterating when the next 
                candidate storage has this name. Defaults to None.

        Returns:
            list[Storage]: a list of storages which mask matches provided tags.

        """
        storages = []
        for storage in self._get_storages():

            if stop_before and storage.name == stop_before:
                break

            if storage_type and storage.type != storage_type:
                continue

            if storage.is_matching(tags):
                storages.append(storage)

        return storages

    def _build_structure(self, item, storage_type=StorageType.CHECKOUT):
        for storage in self._get_matching_storages(item.tags, storage_type):
            storage.build_structure(item.tags, item.fields)

    def _load(self, item, storage_type=StorageType.CHECKOUT, existing_only=True, replicate=True):
        
        storages = self._get_matching_storages(item.tags, storage_type)

        for storage in storages:

            _item = storage.get_item(item.tags, item.fields)
            if not _item or (existing_only and not _item.exists):
                continue
            
            _item.component = item.component

            if not replicate:
                return _item

            return self._save(_item, storage_type, mode=OperationMode.LOAD)

    def _save(self, item, storage_type=StorageType.CHECKOUT, overwrite=False, mode=OperationMode.SAVE):
        is_meta = isinstance(item, MetaItem)

        # item to return from this method,
        # in most cases from local storage
        return_item = None

        # destination items are stored in the same order
        # as storages
        dest_items = []

        stop_before = None
        
        if not is_meta and item.storage and mode == OperationMode.LOAD:
            stop_before = item.storage.name

        storages = self._get_matching_storages(
            item.tags,
            storage_type,
            stop_before
        )

        for storage in reversed(storages):

            dest_item = storage.get_item(item.tags, item.fields)
            if not dest_item:
                continue

            dest_item.component = item.component

            # local storage has to be the last
            return_item = dest_item

            if dest_item.exists and not overwrite:
                continue

            storage.build_structure(item.tags, item.fields)

            dest_items.append(dest_item)

        if dest_items:

            if item.is_sequence:

                index = 1

                while True:

                    data = item.read(index)
                    if data is None:
                        break

                    for dest_item in dest_items:
                        dest_item.write(data, index)

                    index += 1
            else:
                data = item.read()
                for dest_item in dest_items:
                    dest_item.write(data)

        elif mode == OperationMode.SAVE:
            return return_item

        if is_meta:
            return return_item

        return return_item or item

    def _build_item_from_filename(self, filename):
        for storage in self._storages:
            item = storage.get_item_by_filename(filename)
            if item:
                return item

    def create_item(self, tags, fields, **kwargs):
        component = Component.create(tags, fields, kwargs or None)
        
        meta_item = MetaItem.from_component(component)

        target_item = self._load(
            meta_item,
            storage_type=StorageType.CHECKOUT,
            existing_only=False, 
            replicate=False
        )
        self._build_structure(target_item, storage_type=StorageType.CHECKOUT)

        return target_item

    def publish_item(self, item, as_revision=True, comment=None):

        component = item.component
        if not component:
            raise Exception(
                'Unable to find any component in "{}"'.format(item)
            )
        
        if not as_revision:

            # save revision first

            meta_item = MetaItem.from_component(
                component, 
                as_revision=True
            )
            meta_item.filename = item.filename

            target_item = self._save(meta_item, storage_type=StorageType.PUBLISH)
            if not target_item:
                raise Exception('Unable to save item "{}"'.format(meta_item))

        meta_item = MetaItem.from_component(
            component, 
            as_revision=as_revision
        )
        meta_item.filename = item.filename

        target_item = self._save(meta_item, storage_type=StorageType.PUBLISH)
        if not target_item:
            raise Exception('Unable to save item "{}"'.format(meta_item))

        component.publish(as_revision, comment)

        return target_item

    def checkout_item(self, tags, fields, release_version=None, revision_version=None, force=False):
        
        component = Component.find_one(
            tags, fields, 
            max_release_version=release_version, 
            max_revision_version=revision_version
        )
        if not component:
            raise Exception(
                'The item with tags={} and fields={} doesn\'t exist'.format(tags, fields)
            )

        # prepare the latest published revision to be loaded first
        meta_item = MetaItem.from_component(
            component, 
            published_only=True
        )

        component.checkout(force)

        # this item represents the latest published revision
        source_item = self._load(meta_item, storage_type=StorageType.PUBLISH)
        if not source_item:
            return

        # extract '__release__' and '__revision__' fields from component data
        source_item.fields.update(component.get_version_data())
        
        target_item = self._save(source_item, storage_type=StorageType.CHECKOUT)

        return target_item

    # def load_release(self, tags, fields, latest=False):

    #     meta_item = MetaItem(tags, fields)

    #     if '__release__' not in fields or latest:

    #         component = Component.find_one(tags, fields, num_releases=2)
    #         if not component:
    #             return

    #         meta_item = MetaItem.from_component(component, as_revision=False)

    #     meta_item.add_tag('__release__')

    #     item = self._load(meta_item, storage_type=StorageType.PUBLISH)

    #     return item

    # def load_revision(self, tags, fields, update=True):
    #     tags = tags[:]
    #     fields = fields.copy()

    #     release_version = fields.get('__release__')
    #     revision_version = fields.get('__revision__')

    #     if revision_version and not release_version:
    #         raise Exception(
    #             'Release version not provided for storage '
    #             'item with tags={} and fields={}'.format(tags, fields)
    #         )

    #     if not release_version or not revision_version:

    #         component = Component.find_one(tags, fields, num_releases=2)
    #         if not component:
    #             raise Exception(
    #                 'Component with tags={} and fields={} doesn\'t'.format(
    #                     tags, fields
    #                 )
    #             )

    #         if release_version:
    #             release = next(
    #                 (
    #                     rel for rel in component.releases 
    #                     if rel.version == release_version
    #                 ), None
    #             )
    #             if not release:
    #                 raise Exception((
    #                     'Unable to find release "{}" for '
    #                     'storage item with tags={} and fields={}'
    #                 ).format(release_version, tags, fields))
    #         else:
    #             # get latest published release
    #             release = next(
    #                 (rel for rel in component.releases if rel.published), None
    #             )
            
    #         fields['__release__'] = release.version

    #         if revision_version:
    #             revision = next(
    #                 (
    #                     rev for rev in release.revisions
    #                     if rev.version == revision_version
    #                 ), None
    #             )
    #             if not revision:
    #                 raise Exception((
    #                     'Unable to find revision "{}" for '
    #                     'storage item with tags={} and fields={}'
    #                 ).format(revision_version, tags, fields))

    #         if not release:
    #             # TODO: raise error because the component has not ever got published
    #             return
                
    #             release_version = release.version

    #     if '__revision__' not in tags:
    #         tags.append('__revision__')

    #     item = self._load(
    #         MetaItem(tags, fields), 
    #         storage_type=StorageType.PUBLISH
    #     )

    #     return item

    def load_item_by_filename(self, filename, latest=False):

        item = self._build_item_from_filename(filename)
        if not item:
            raise Exception(
                'The item with filename "{}" doesn\'t exist'.format(filename)
            )

        component = Component.find_one(item.tags, item.fields, num_releases=None)    
        if not component:
            return
            
        if latest:
            
            component.
            if '__release__' not in item.tags:
                
            release = next((rel for rel in component.releases if rel.published), None)
            if not release:
                # TODO: raise error because the component has not ever got published
                return

        item = self._load(item)

        return item