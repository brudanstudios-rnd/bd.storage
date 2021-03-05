import sys
import logging
from contextlib import contextmanager

from bd.api import Session

from ._vendor.six import reraise
from . import storage as st
from . import queries
from .errors import *

log = logging.getLogger(__name__)


class Revision(object):

    def __init__(self, revision_data):
        self.component = None
        for key, val in revision_data.items():
            setattr(self, key, val)

    @contextmanager
    def publish(self, comment=None):
        storage_item = self.get_storage_item()
        if comment:
            storage_item.set_metadata('note', comment)

        yield storage_item

        try:
            Session().execute(
                queries.PUBLISH_REVISION_MUTATION,
                {"revision_id": self.id, "comment": comment}
            )
        except:
            error_message, error_traceback = sys.exc_info()[1:]

            try:
                storage_item.remove()
            except StorageError as e:
                log.warning(
                    'Unable to cleanup data after the failed revision '
                    'publish. {}'.format(str(e))
                )

            reraise(RevisionPublishError, error_message, error_traceback)
        else:
            self.comment = comment
            self.published = True

    def change_ownership(self, user_data):
        try:
            Session().execute(
                queries.CHANGE_REVISION_OWNERSHIP_MUTATION,
                {"revision_id": self.id, "user_id": user_data['id']}
            )
        except:
            reraise(ChangeOwnershipError, *sys.exc_info()[1:])
        else:
            self.user = user_data

    def get_storage_item(self, checkout=False):
        tags = st.TagsEdit(self.component.tags)

        fields = st.FieldsEdit(self.component.fields).update_fields({
            '_version_': self.version
        })

        meta_item = self.component.pool.get_item(tags)
        if checkout:
            meta_item = self._convert_to_checkout_item(meta_item)

        return meta_item.get_storage_item(fields)

    def _convert_to_checkout_item(self, published_item):
        tags = st.TagsEdit(published_item.tags)
        tags.add_tag('_checkout_')

        checkout_item = self.component.pool.get_item(tags)
        if not checkout_item:
            return

        # get the item from the last available storage
        upstrem_checkout_item = checkout_item.get_upstream_item()
        upstrem_checkout_item.set_next_item(published_item)

        return checkout_item

    def to_dict(self, caller=None):
        d = {}
        for attr_name, attr_value in self.__dict__.items():

            if attr_name == 'component':

                # if called directly from the class instance
                if not caller:
                    d[attr_name] = attr_value.to_dict(self)

                continue

            d[attr_name] = attr_value

        return d

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (
            "Revision(id={0}, version={1}, published={2}, comment={3})"
        ).format(
            self.id,
            self.version,
            self.published,
            self.comment
        )


class Component(object):

    def __init__(self, storage_pool, component_data):
        self.pool = storage_pool
        self.revisions = []
        for key, val in component_data.items():
            if key == 'revisions':
                for revision_data in val:
                    revision = Revision(revision_data)
                    revision.component = self
                    self.revisions.append(revision)
            else:
                setattr(self, key, val)

    def get_revision(self, published=None, version=None):
        if version is not None:
            return next((r for r in self.revisions if r.version == version), None)
        if published is not None:
            return next((r for r in self.revisions if r.published == published), None)
        return self.revisions[0]

    def checkout(self, force_ownership=False):
        latest_revision = self.get_revision()

        if latest_revision.published:
            latest_revision = self.create_revision()
        else:
            try:
                current_user = Session().current_user()
            except:
                reraise(UserRequestError, *sys.exc_info()[1:])
            else:
                if latest_revision.user['id'] != current_user['id']:
                    if not force_ownership:
                        raise RevisionOwnershipError(
                            'Revision is already checked out by "{}". '
                            'Please contact that person to resolve.'.format(
                                latest_revision.user['email']
                            )
                        )

                    latest_revision.change_ownership(current_user)

        return latest_revision

    def create_revision(self):
        try:
            data = Session().execute(
                queries.CREATE_REVISION_MUTATION,
                {"component_id": self.id}
            )
        except:
            reraise(RevisionCreateError, *sys.exc_info()[1:])
        else:
            revision_data = data['createComponentRevision']

            revision = Revision(revision_data)
            revision.component = self

            self.revisions.insert(0, revision)

            return revision

    def to_dict(self, caller=None):
        d = {}
        for attr_name, attr_value in self.__dict__.items():

            if attr_name == 'pool':
                continue

            if attr_name == 'revisions':

                if caller:
                    continue

                revision_data_list = []

                for revision in attr_value:
                    revision_data_list.append(revision.to_dict(self))

                attr_value = revision_data_list

            d[attr_name] = attr_value

        return d

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

