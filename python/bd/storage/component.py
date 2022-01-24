import os
import sys
import uuid
import logging
import tempfile
from collections import namedtuple
from contextlib import contextmanager

from bd.api import Session

from six import reraise

from .edits import TagsEdit
from . import queries
from .core import StoragePool, Identifier, MetaItem
from .errors import *

log = logging.getLogger(__name__)


Transaction = namedtuple('Transaction', ['temp', 'item'])


class Revision(object):

    def __init__(self, component, **data):
        self.__dict__.update(data)
        self._component = component

    @contextmanager
    def publish(self, comment=None, storage_pool=None):
        if not storage_pool:
            storage_pool = StoragePool.get_global_instance()
            if not storage_pool:
                raise RevisionPublishError('StoragePool instance not initialized.')

        revision_id = getattr(self, 'id')

        storage_item = self.get_storage_item(storage_pool=storage_pool)

        if comment:
            storage_item.set_metadata('note', comment)

        transaction = Transaction(
            os.path.join(tempfile.gettempdir(), uuid.uuid1().hex),
            storage_item
        )

        try:
            yield transaction

            if os.path.exists(transaction.temp):
                with open(transaction.temp, 'rb') as f:
                    storage_item.write(f.read(), with_metadata=True)
        finally:
            if os.path.exists(transaction.temp):
                os.remove(transaction.temp)

        try:
            Session().execute(
                queries.PUBLISH_REVISION_MUTATION,
                {"revision_id": revision_id, "comment": comment}
            )
        except Exception as e:
            reraise(RevisionPublishError, RevisionPublishError(e), sys.exc_info()[2])

        setattr(self, 'comment', comment)
        setattr(self, 'published', True)

    def acquire(self):
        try:
            revision_id = getattr(self, 'id')

            session = Session()

            user_id = session.get_user_id()

            session.execute(
                queries.ACQUIRE_REVISION_MUTATION,
                {"revision_id": revision_id, "user_id": user_id}
            )
        except Exception as e:
            reraise(RevisionAcquireError, RevisionAcquireError(e), sys.exc_info()[2])

        setattr(self, 'user_id', user_id)

    def get_storage_item(self, checkout=False, storage_pool=None):
        if not storage_pool:
            storage_pool = StoragePool.get_global_instance()
            if not storage_pool:
                raise RevisionPublishError('StoragePool instance not initialized.')

        identifier = self._component.identifier.copy()
        identifier.set_field('_version_', self.version)

        meta_item = storage_pool.get_item(identifier.tags)
        if checkout:
            meta_item = self._checkout(meta_item, storage_pool)

        return meta_item.get_storage_item(identifier.fields)

    def remove(self):
        try:
            revision_id = getattr(self, 'id')

            session = Session()

            session.execute(
                queries.REMOVE_REVISION_MUTATION,
                {"id": revision_id}
            )
        except Exception as e:
            reraise(RevisionRemoveError, RevisionRemoveError(e), sys.exc_info()[2])

    def _checkout(self, published_item, storage_pool):
        """

        Args:
            published_item (MetaItem):
            storage_pool (StoragePool):

        Returns:
            MetaItem:
        """
        tags = TagsEdit(published_item.tags)
        tags.add_tag('_checkout_')

        checkout_item = storage_pool.get_item(tags)
        if not checkout_item:
            return

        checkout_item.add_upstream_item(published_item)

        return checkout_item

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (
            "Revision(id={0}, version={1}, published={2}, comment='{3}')"
        ).format(
            getattr(self, 'id', ''),
            getattr(self, 'version', ''),
            getattr(self, 'published', ''),
            getattr(self, 'comment', '')
        )


class Component(object):

    @classmethod
    def find_components(cls, tags, fields, limit=100):
        try:
            data = Session().execute(
                queries.FIND_COMPONENTS_QUERY,
                {
                    'tags': tags,
                    'fields': fields,
                    'limit': limit
                }
            )['components']
        except Exception as e:
            reraise(ComponentError, ComponentError(e), sys.exc_info()[2])

        components = []

        for cmp_data in data:
            identifier = Identifier(cmp_data['tags'], cmp_data['fields'])
            component = cls(identifier)
            component._id = cmp_data['id']
            components.append(component)

        return components

    def __init__(self, identifier):
        self.identifier = identifier.pure()
        self._id = None

    @property
    def tags(self):
        return self.identifier.tags

    @property
    def fields(self):
        return self.identifier.fields

    @property
    def id(self):
        if self._id is None:
            self._id = self.identifier.hash()
        return self._id

    def revisions(self, limit=10):
        try:
            data = Session().execute(
                queries.GET_REVISIONS_QUERY,
                {
                    'id': self.id,
                    'limit': limit
                }
            )['component_revisions']
        except Exception as e:
            reraise(RevisionsGetError, RevisionsGetError(e), sys.exc_info()[2])

        revisions = []

        for rv_data in data:
            revisions.append(
                Revision(self, **rv_data)
            )

        return revisions

    def latest_revision(self):
        revisions = self.revisions(1)
        if revisions:
            return next(iter(revisions), None)

    def create_revision(self, force_ownership=False):
        try:
            session = Session()
            result = session.execute(
                queries.CREATE_REVISION_MUTATION,
                {
                    "id": self.id,
                    "tags": self.tags,
                    "fields": self.fields
                }
            )
            log.debug(result)
            data = result['insert_component_revisions_one']
        except Exception as e:
            reraise(RevisionCreateError, RevisionCreateError(e), sys.exc_info()[2])

        user_data = data.pop('user')

        revision = Revision(self, **data)

        if data['user_id'] == session.get_user_id():
            return revision

        if force_ownership:
            revision.acquire()
            return revision

        raise RevisionOwnershipError(
            'Revision is owned by "{}". '
            'Please contact that person to resolve.'.format(
                user_data['email']
            )
        )

    def remove(self):
        try:
            session = Session()

            session.execute(
                queries.REMOVE_COMPONENT_MUTATION,
                {"id": self.id}
            )
        except Exception as e:
            reraise(ComponentRemoveError, ComponentRemoveError(e), sys.exc_info()[2])

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (
            "Component(id={0}, tags={1}, fields={2})"
        ).format(
            self.id,
            repr(self.tags),
            repr(self.fields)
        )
