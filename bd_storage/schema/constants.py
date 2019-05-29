import re
import sys


class _Const:

    def __init__(self):
        self._data = {
            'template_key_regex': re.compile(r"\{([a-zA-Z0-9\.\_\-\[\]]+)(?:\:.+)?\}"),
            'template_filename_regex': re.compile(r"^\(((?:[\w]+\-?)+)\)\.yml$")
        }

    @property
    def template_key_regex(self):
        return self._data['template_key_regex']

    @property
    def template_filename_regex(self):
        return self._data['template_filename_regex']


sys.modules[__name__] = _Const()
