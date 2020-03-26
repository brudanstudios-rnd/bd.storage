import sys
import logging

from bd.api import Session
import bd.api.errors as err

from . import utils
from .component import Component
from .storage import MetaItem
from . import queries

this = sys.modules[__name__]
this._log = logging.getLogger(__name__)


class VCS(object):

    def __init__(self, storage_pool):
        self._pool = storage_pool

    def create_component(self, tags, fields, metadata=None):

        tags = utils.remove_extra_tags(tags)
        fields = utils.remove_extra_fields(fields)

        component_id = utils.create_id(tags, fields)

        data = Session().execute(
            queries.CREATE_COMPONENT_MUTATION,
            {"id": component_id, "tags": tags, "fields": fields, "metadata": metadata}
        )

        component_data = data['createComponents']['returning'][0]

        return Component(**component_data)

    def get_item_from_component(self, component, as_revision=True, as_published=False):

        meta_item = MetaItem(component.tags, component.fields)
        meta_item.set_userdata('_component_', component)

        meta_item.add_tags(
            '_publish_' if as_published else '_checkout_',
            '_revision_' if as_revision else '_release_'
        )
        meta_item.set_fields({
            '_release_': component.current_release.version,
            '_revision_': component.current_revision.version
        })

        return self._pool.load_item(
            meta_item,
            existing_only=False,
            download=False
        )

    def _get_component_by_id(self, component_id):
        data = Session().execute(queries.FIND_COMPONENT_QUERY, {"id": component_id})
        if data['getComponent']:
            component_data = data['getComponent']
            return Component(**component_data)

    # def find_entity(self, tags, fields):
    #
    #     tags = utils.remove_extra_tags(tags)
    #     fields = utils.remove_extra_fields(fields)
    #
    #     component = self._get_component_by_id(
    #         utils.create_id(tags, fields)
    #     )
    #     if release

    def publish(self, item, as_revision=True, comment=None):

        component = item.get_userdata('_component_')
        if not component:
            raise Exception(
                'Unable to extract component from "{}"'.format(item)
            )

        if not as_revision:

            # save revision first

            meta_item = self.build_item_from_component(
                component,
                as_revision=True
            )
            meta_item.filename = item.filename

            target_item = self._pool.save_item(meta_item)
            if not target_item:
                raise Exception('Unable to save item "{}"'.format(meta_item))

        meta_item = self.build_item_from_component(
            component,
            as_revision=as_revision
        )
        meta_item.filename = item.filename

        target_item = self._pool.save_item(meta_item)
        if not target_item:
            raise Exception('Unable to save item "{}"'.format(meta_item))

        if as_revision:
            component.get_release().get_revision().publish(comment)
        else:
            component.get_release().publish(comment)

        return target_item

    def checkout(self, item, force_ownership=False):
        tags, fields = item.common_tags, item.common_fields
        component = item.get_userdata('_component_')
        if not component:
            raise Exception(
                'Unable to find any component in "{}"'.format(item)
            )

        # prepare the latest published revision to be loaded first
        meta_item = self.build_item_from_component(
            component,
            published_only=True
        )

        # this item represents the latest published revision
        source_item = self._pool.load_item(meta_item)
        if not source_item:
            return

        source_item.remove_tags('_publish_', '_revision_').add_tag('_checkout_')

        component.checkout(force_ownership)

        # extract '__release__' and '__revision__' fields from component data
        source_item.set_fields(component.get_version_data())

        target_item = self._pool.save_item(source_item)

        return target_item

    def load(self, vcs_entity):
        pass

    # def load_release(self, tags, fields, latest=False):

    #     meta_item = MetaItem(tags, fields)

    #     if '__release__' not in fields or latest:

    #         component = Component.find_one(tags, fields, num_releases=2)
    #         if not component:
    #             return

    #         meta_item = MetaItem.from_component(component, as_revision=False)

    #     meta_item.add_tag('__release__')

    #     item = self.load_item(meta_item, storage_type=StorageType.PUBLISH)

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

    #     item = self.load_item(
    #         MetaItem(tags, fields),
    #         storage_type=StorageType.PUBLISH
    #     )

    #     return item

    # def load_item_by_filename(self, filename, latest=False):
    #
    #     item = self._build_item_from_filename(filename)
    #     if not item:
    #         raise Exception(
    #             'The item with filename "{}" doesn\'t exist'.format(filename)
    #         )
    #
    #     component = Component.find_one(item.tags, item.fields, num_releases=None)
    #     if not component:
    #         return
    #
    #     if latest:
    #
    #         if '__release__' not in item.tags:
    #
    #         release = next((rel for rel in component.releases if rel.published), None)
    #         if not release:
    #             # TODO: raise error because the component has not ever got published
    #             return
    #
    #     item = self.load_item(item)
    #
    #     return item

    @classmethod
    def make_item_from_component(cls,
                                 component,
                                 release_number=None,
                                 revision_number=None,
                                 as_revision=True,
                                 published_only=False):
        meta_item = MetaItem(
            component.tags,
            component.fields
        )

        meta_item.set_fields(component.get_version_data(as_revision, published_only))
        meta_item.component = component
        meta_item.add_tags('_publish_', '_revision_' if as_revision else '_release_')

        return meta_item
