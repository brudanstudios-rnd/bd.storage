__all__ = ["Schema"]

import logging

from .item import SchemaDir, SchemaAnchor
from ..utils import putils
from ..errors import *

log = logging.getLogger(__name__)


class Schema(object):

    cached_anchors = {}

    def __init__(self, schema_dir):
        self._schema_dir = schema_dir

    def get_items(self):
        anchor_items = self.cached_anchors.get(self._schema_dir)

        if not anchor_items:

            anchor_items = {}

            for root, dirnames, filenames in putils.walk(self._schema_dir):

                if root == self._schema_dir:
                    continue

                SchemaDir.create(schema_id=self._schema_dir, path=root)

                for filename in filenames:

                    if not filename.endswith(".yml"):
                        continue

                    # skip .yml files which names match
                    # any directory name on the same level
                    # because 'walk' will eventually enter those
                    # directories and create SchemaDir for them
                    if filename[:-4] in dirnames:
                        continue

                    schema_anchor = SchemaAnchor.create(
                        schema_id=self._schema_dir, path=putils.join(root, filename)
                    )

                    tags = schema_anchor.tags
                    if not tags:
                        continue

                    anchor_items[frozenset(tags)] = schema_anchor

            self.cached_anchors[self._schema_dir] = anchor_items

        return anchor_items

    def get_item(self, tags):
        return self.get_items().get(frozenset(tags))
