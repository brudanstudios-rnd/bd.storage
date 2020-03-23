import sys
import hashlib
import logging

from bd.api import Session

from .storage import MetaItem, StoragePool

from . import queries
from . import utils

this = sys.modules[__name__]
this._log = logging.getLogger(__name__)


class Revision(object):
    
    def __init__(self, **revision_data):
        self.release = None
        for key, val in revision_data.items():
            setattr(self, key, val)

    def publish(self, comment=None):
        session = Session()
        session.execute(
            queries.CHANGE_REVISION_STATUS_MUTATION,
            {"revision_id": self.id, "comment": comment}
        )
        self.comment = comment
        self.published = True

    def change_ownership(self, user_data):
        session = Session()
        session.execute(
            queries.CHANGE_REVISION_OWNERSHIP_MUTATION,
            {"revision_id": self.id, "user_id": user_data['id']}
        )
        self.user = user_data

    def to_dict(self):
        d = {}
        for attr_name, attr_value in self.__dict__.items():
            
            if attr_name == 'release':
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


class Release(object):

    def __init__(self, **release_data):
        self.component = None
        self.revisions = []
        for key, val in release_data.items():
            if key == 'revisions':
                for revision_data in val:
                    revision = Revision(**revision_data)
                    revision.release = self
                    self.revisions.append(revision)
            else:
                setattr(self, key, val)

    def create_revision(self):
        session = Session()

        data = session.execute(
            queries.CREATE_REVISION_MUTATION,
            {"release_id": self.id}
        )
        if data['createComponentRevisions']:
            revision_data = data['createComponentRevisions']['returning'][0]

            revision = Revision(**revision_data)
            revision.release = self

            self.revisions.insert(0, revision)
            return revision

    def publish(self, comment=None):

        revision = self.revisions[0]

        Session().execute(
            queries.PUBLISH_RELEASE_MUTATION,
            {"release_id": self.id, "revision_id": revision.id, "comment": comment}
        )
        self.published = True
        revision.comment = comment
        revision.published = True

    def to_dict(self):
        d = {}
        for attr_name, attr_value in self.__dict__.items():
            
            if attr_name == 'component':
                continue

            if attr_name == 'revisions':
                
                revision_data_list = []
                
                for revision in attr_value:
                    revision_data_list.append(revision.to_dict())
                
                attr_value = revision_data_list
            
            d[attr_name] = attr_value

        return d

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (
            "Release(id={0}, version={1}, published={2})"
        ).format(
            self.id,
            self.version,
            self.published
        )


class Component(object):

    @classmethod
    def create(cls, tags, fields, metadata=None):

        tags = utils.remove_extra_tags(tags)
        fields = utils.remove_extra_fields(fields)

        component_id = utils.create_id(tags, fields)

        data = Session().execute(
            queries.CREATE_COMPONENT_MUTATION,
            {"id": component_id, "tags": tags,
                "fields": fields, "metadata": metadata}
        )
        if data['createComponents']:
            component_data = data['createComponents']['returning'][0]
            return cls(**component_data)

    @classmethod
    def get_component(cls, 
                      component_id, 
                      num_releases=1, 
                      num_revisions=1, 
                      max_release_version=None, 
                      max_revision_version=None):

        data = Session().execute(
            queries.FIND_COMPONENT_QUERY,
            {
                "id": component_id, 
                "num_releases": num_releases, 
                "num_revisions": num_revisions,
                "max_release_version": max_release_version,
                "max_revision_version": max_revision_version
            }
        )

        if data['getComponent']:
            component_data = data['getComponent']
            return cls(**component_data)

    @classmethod
    def find_one(cls, 
                 tags, fields, 
                 num_releases=1, 
                 num_revisions=1, 
                 max_release_version=None, 
                 max_revision_version=None):
        
        tags = utils.remove_extra_tags(tags)
        fields = utils.remove_extra_fields(fields)

        component_id = utils.create_id(tags, fields)

        return cls.get_component(
            component_id, 
            num_releases, 
            num_revisions, 
            max_release_version, 
            max_revision_version
        )

    def __init__(self, **component_data):
        self.releases = []
        for key, val in component_data.items():
            if key == 'releases':
                for release_data in val:
                    release = Release(**release_data)
                    release.component = self
                    self.releases.append(release)
            else:
                setattr(self, key, val)

    def publish(self, for_review=True, comment=None):
        release = self.releases[0]
        revision = release.revisions[0]
        if for_review:
            revision.publish(comment)
        else:
            release.publish(comment)

    def get_last_release(self, published=False):
        if published:
            for release in self.releases:
                if release.published:
                    return release
        else:
            return self.releases[0] if self.releases else None

    def get_last_revision(self, published=False):
        if published:
            for release in self.releases:
                for revision in release.revisions:
                    if revision.published:
                        return revision
        else:
            last_release = self.releases[0] if self.releases else None
            return last_release.revisions[0]

    def checkout(self, force_ownership=False):

        last_release = self.releases[0] if self.releases else None

        # if component has been just created or re
        if not last_release or last_release.published:
            self._create_release()
        else:
            last_revision = last_release.revisions[0]
            
            if not last_revision.published:
                
                current_user = Session().current_user()
                if last_revision.user['id'] == current_user['id']:
                    return

                if not force_ownership:
                    raise Exception(
                        'The item is already checked out by "{}". '
                        'Please contact this person to resolve.'.format(
                            last_revision.created_by['email']
                        )
                    )

                last_revision.change_ownership(Session().current_user())
            else:
                last_release.create_revision()

    def get_version_data(self, as_revision=True, published_only=False):
        version_data = {}

        if as_revision:
            for release in self.releases:
                for revision in release.revisions:
                    
                    if published_only and not revision.published:
                        continue
                    
                    version_data['_release_'] = release.version
                    version_data['_revision_'] = revision.version
                    
                    return version_data
        else:
            if published_only:

                # get the latest published release
                release = next(
                    (rel for rel in self.releases if rel.published), None
                )
            else:
                release = self.releases[0]

            if not release:
                raise Exception('The component has never been released')

            version_data['_release_'] = release.version
            version_data['_revision_'] = release.revisions[0].version
        
            return version_data

    def to_dict(self):
        d = {}
        for attr_name, attr_value in self.__dict__.items():
            
            if attr_name == 'releases':
                
                release_data_list = []
                
                for release in attr_value:
                    release_data_list.append(release.to_dict())
                
                attr_value = release_data_list
            
            d[attr_name] = attr_value

        return d
        
    def _create_release(self):
        session = Session()

        data = session.execute(
            queries.CREATE_RELEASE_MUTATION,
            {"component_id": self.id}
        )
        if data['createComponentReleases']:
            release_data = data['createComponentReleases']['returning'][0]

            release = Release(**release_data)
            release.component = self

            self.releases.insert(0, release)

            return release

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

