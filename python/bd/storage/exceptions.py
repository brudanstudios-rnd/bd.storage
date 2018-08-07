import sys
import traceback


class Error(Exception):

    default_message = "Unspecified error occured."

    def __init__(self, message=None, details=None):
        """Initialize exception with 'message'.

        Kwargs:
            message (str): if None, the 'default_message' will be used.
            details (dict): extra information that can be used in the message
                and also provide more context.

        """
        if message is None:
            message = self.default_message

        self.message = message
        self.details = details if details else {}
        self.traceback = traceback.format_exc()

    def __str__(self):
        details = {}
        for key, value in self.details.iteritems():
            if isinstance(value, unicode):
                value = value.encode(sys.getfilesystemencoding())
            details[key] = value

        return str(self.message.format(**details))

