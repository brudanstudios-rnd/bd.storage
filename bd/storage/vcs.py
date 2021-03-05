import sys
import logging

from bd.api import Session

from ._vendor.six import reraise
from . import utils
from .errors import *
from .component import Component
from . import queries

log = logging.getLogger(__name__)


class VCS(object):

    def __init__(self, storage_pool):
        self._pool = storage_pool

    def add_component(self, tags, fields, metadata=None):

        tags = utils.remove_extra_tags(tags)
        fields = utils.remove_extra_fields(fields)

        component_id = utils.create_id(tags, fields)

        try:
            data = Session().execute(
                queries.CREATE_COMPONENT_MUTATION,
                {
                    "id": component_id,
                    "tags": tags,
                    "fields": fields,
                    "metadata": metadata
                }
            )
        except:
            reraise(ComponentCreateError, *sys.exc_info()[1:])
        else:
            component_data = data['createComponent']
            if component_data:
                return Component(self._pool, component_data)

    def get_component(self, tags, fields):
        tags = utils.remove_extra_tags(tags)
        fields = utils.remove_extra_fields(fields)

        component_id = utils.create_id(tags, fields)

        try:
            data = Session().execute(
                queries.FIND_COMPONENT_QUERY,
                {
                    "id": component_id
                }
            )
        except:
            reraise(ComponentFindError, *sys.exc_info()[1:])
        else:
            component_data = data['getComponent']
            if component_data:
                return Component(self._pool, component_data)

