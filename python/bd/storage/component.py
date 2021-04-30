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

    def __init__(self, revision_data):
        self.component = None
        self.__dict__.update(revision_data)

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
        except Exception as e:
            reraise(RevisionPublishError, RevisionPublishError(e), sys.exc_info()[2])
        else:
            self.comment = comment
            self.published = True

    def change_owner(self, user_data):
        try:
            Session().execute(
                queries.CHANGE_REVISION_OWNERSHIP_MUTATION,
                {"revision_id": self.id, "user_id": user_data['id']}
            )
        except Exception as e:
            reraise(ChangeOwnershipError, ChangeOwnershipError(e), sys.exc_info()[2])
        else:
            self.user = user_data

    def get_storage_item(self, checkout=False):
        tags = TagsEdit(self.component.tags)

        fields = FieldsEdit(self.component.fields).update_fields({
            '_version_': self.version
        })

        meta_item = self.component.pool.get_item(tags)
        if checkout:
            meta_item = self._checkout(meta_item)

        return meta_item.get_storage_item(fields)

    def _checkout(self, published_item):
        tags = TagsEdit(published_item.tags)
        tags.add_tag('_checkout_')

        checkout_item = self.component.pool.get_item(tags)
        if not checkout_item:
            return

        checkout_item.add_upstream_item(published_item)

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

    def __init__(self, tags, fields):
        self.tags = utils.remove_extra_tags(tags)
        self.fields = utils.remove_extra_fields(fields)

        self.id = utils.create_id(tags, fields)

    def get_revisions(self, limit=10):
        try:
            data = Session().execute(
                queries.GET_REVISIONS_QUERY,
                {
                    'id': self.id,
                    'limit': limit
                }
            )
        except Exception as e:
            reraise(RevisionsGetError, RevisionsGetError(e), sys.exc_info()[2])
        else:
            revisions = []

            query_result = data['getComponentRevisions']

            if query_result:
                for revision_data in query_result:
                    revision = Revision(revision_data)
                    revision.component = self
                    revisions.append(revision)

            return revisions

    def create_revision(self, force_ownership=False):
        revision = None
        try:
            data = Session().execute(
                queries.CREATE_REVISION_MUTATION,
                {
                    "id": self.id,
                    "tags": self.tags,
                    "fields": self.fields
                }
            )
        except Exception as e:
            reraise(RevisionCreateError, RevisionCreateError(e), sys.exc_info()[2])
        else:
            revision_data = data['createComponentRevision']

            revision = Revision(revision_data)
            revision.component = self

        # else:
        #     try:
        #         current_user = Session().current_user()
        #     except:
        #         reraise(UserRequestError, *sys.exc_info()[1:])
        #     else:
        #         if revision.user['id'] != current_user['id']:
        #             if not force_ownership:
        #                 raise RevisionOwnershipError(
        #                     'Revision is already checked out by "{}". '
        #                     'Please contact that person to resolve.'.format(
        #                         revision.user['email']
        #                     )
        #                 )
        #
        #             revision.change_owner(current_user)

        return revision

    def _update_from_dict(self, data):

        supported_keys = frozenset(('id', 'tags', 'fields', 'created_at', 'revisions'))

        for key, value in data.items():

            if key not in supported_keys:
                continue

            if key == 'revisions':
                self.revisions = []
                for revision_data in value:
                    revision = Revision(revision_data)
                    revision.component = self
                    self.revisions.append(revision)
            else:
                setattr(self, key, value)

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


class ComponentFactory(object):

    def __init__(self, storage_pool):
        self._pool = storage_pool

    def get_component(self, tags, fields):
        tags, fields = self._prepare_data(tags, fields)
        _id = utils.create_id(tags, fields)
        return Component(id=_id, tags=tags, fields=fields)

    # def add_component(self, tags, fields):
    #     tags, fields = self._prepare_data(tags, fields)
    #     component_id = utils.create_id(tags, fields)
    #
    #     try:
    #         data = Session().execute(
    #             queries.ENSURE_COMPONENT_MUTATION,
    #             {
    #                 "id": component_id,
    #                 "tags": tags,
    #                 "fields": fields
    #             }
    #         )
    #     except:
    #         reraise(ComponentCreateError, *sys.exc_info()[1:])
    #     else:
    #         component_data = data['createComponent']
    #         if component_data:
    #             return Component(self._pool, component_data)

    def _prepare_data(self, tags, fields):
        tags = utils.remove_extra_tags(tags)
        fields = utils.remove_extra_fields(fields)

        if 'project' not in fields:
            fields['project'] = self._pool.project

        return tags, fields
