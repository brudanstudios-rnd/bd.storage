import datetime
import os
import re
import hashlib
import posixpath

from bd import hooks as bd_hooks

from .edits import FieldsEdit, TagsEdit


def create_uid(tags, fields):
    return hashlib.md5(
        str(tuple(sorted(tags)) + tuple(sorted(fields.items()))).encode("UTF8")
    ).hexdigest()


def remove_extra_fields(fields):
    return FieldsEdit(fields).remove_extra_fields().fields


def remove_extra_tags(tags):
    return TagsEdit(tags).remove_extra_tags().tags


def parse_mask(mask):
    return list(
        filter(
            None,
            re.split(
                r"([\(\)\|\&])",
                mask.replace(" ", "").replace("||", "|").replace("&&", "&"),
            ),
        )
    )


def match_tags(mask, tags):
    """Check whether the tags match the provided mask.

    Args:
        mask (list[str] or str): parsed or not parsed tag mask.
        tags (list[str]): list of tags to match.

    Returns:
        bool: True if matches, False otherwise.

    """
    if not isinstance(mask, list):
        mask = parse_mask(mask)

    expression = []

    for item in mask:
        if item in "()":
            expression.append(item)
        elif item == "|":
            expression.append("or")
        elif item == "&":
            expression.append("and")
        elif item == "^":
            expression.append("not")
        else:
            if item[0] == "^":
                expression.append(str(item[1:] not in tags))
            else:
                expression.append(str(item in tags))

    try:
        return eval(" ".join(expression), None, None)
    except:
        return False


class PathUtils(object):
    def walk(self, *args, **kwargs):
        for root, dirnames, filenames in os.walk(*args, **kwargs, followlinks=True):
            yield root.replace("\\", "/"), dirnames, filenames

    def _normpath(self, path):
        if not path:
            return path
        return self.normpath(path)

    def __getattr__(self, item):
        if item in "normpath":
            return lambda path: os.path.normpath(path).replace("\\", "/")
        elif item == "join":
            return lambda *args: posixpath.join(*list(map(self._normpath, args)))
        elif item == "dirname":
            return lambda path: os.path.dirname(self.normpath(path))
        return getattr(os.path, item)


putils = PathUtils()


def json_encoder(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.strftime("%m/%d/%Y %H:%M:%S")
    raise TypeError("Type {} not serializable".format(type(obj)))


def load_hooks():
    """Load hooks stored under current package."""
    bd_hooks.load([putils.join(putils.dirname(__file__), "hooks")])
