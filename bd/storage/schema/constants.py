import re
import sys


class _Const:

    def __init__(self):
        self._data = {
            'template_key_regex': re.compile(r"\{([a-zA-Z0-9\.\_\-\[\]]+)(?:\:.+)?\}"),
        }

    @property
    def template_key_regex(self):
        return self._data['template_key_regex']


sys.modules[__name__] = _Const()
