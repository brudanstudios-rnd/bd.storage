import sys
import logging
from contextlib import contextmanager

from bd.api import Session

from six import reraise

from .edits import TagsEdit, FieldsEdit
from . import queries
from . import utils
from .core import StoragePool
from .errors import *

log = logging.getLogger(__name__)


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

        yield storage_item

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

        tags = TagsEdit(self._component.tags)

        fields = FieldsEdit(self._component.fields).update_fields({
            '_version_': self.version
        })

        meta_item = storage_pool.get_item(tags)
        if checkout:
            meta_item = self._checkout(meta_item, storage_pool)

        return meta_item.get_storage_item(fields)

    def _checkout(self, published_item, storage_pool):
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

    def __init__(self, tags, fields):
        self.tags = utils.remove_extra_tags(tags)
        self.fields = utils.remove_extra_fields(fields)

        self.id = utils.create_id(tags, fields)

    def revisions(self, limit=10):
        try:
            data = Session().execute(
                queries.GET_REVISIONS_QUERY,
                {
                    'id': self.id,
                    'limit': limit
                }
            )['getComponentRevisions']
        except Exception as e:
            reraise(RevisionsGetError, RevisionsGetError(e), sys.exc_info()[2])

        revisions = []

        for rv_data in data:
            revisions.append(
                Revision(self, **rv_data)
            )

        return revisions

    def create_revision(self, force_ownership=False):
        try:
            session = Session()
            data = session.execute(
                queries.CREATE_REVISION_MUTATION,
                {
                    "id": self.id,
                    "tags": self.tags,
                    "fields": self.fields
                }
            )['createComponentRevision']
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
