import re


TMPL_KEY_REGEX = re.compile(r"\{([a-zA-Z0-9\.\_\-\[\]]+)(?:\:.+)?\}")
TMPL_FILENAME_REGEX = re.compile(r"^\<((?:[\w\-]+\:?)+)\>\.yml$")