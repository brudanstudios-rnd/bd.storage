import sys
import traceback


class Error(Exception):

    default_message = "Unspecified error occurred"

    def __init__(self, message=None, details=None):

        if not message:
            message = self.default_message

        self.message = message

        if details is None:
            details = {}

        self.details = details

        self.traceback = traceback.format_exc()

    def __str__(self):
        details = {}
        for key, value in self.details.iteritems():
            if isinstance(value, unicode):
                value = value.encode(sys.getfilesystemencoding())
            details[key] = value
        return str(self.message.format(**details))


class PipelineNotActivatedError(Error):
    default_message = ("Pipeline is not activated yet. "
               "Check if 'BD_PIPELINE_DIR' environment variable exists")


class FilesystemError(Error):
    pass


class FilesystemPathNotFoundError(FilesystemError):
    default_message = "Filesystem path '{path}' not found"


class OverwriteNotPermittedError(FilesystemError):
    default_message = "You're not alowed to overwrite already existing path '{path}'"


class UnableToMakeDirectoryError(FilesystemError):
    default_message = "Unable to make directory '{dirname}'. {exc_msg}"


class ConfigurationError(Error):
    pass


class MandatoryKeyNotFoundError(ConfigurationError):
    default_message = "Mandatory key '{key}' could not be found in any of the configuration files"


class FailedConfigParsingError(ConfigurationError):
    default_message = "Failed to parse configuration: {exc_msg}"


class ProjectPresetNotFoundError(ConfigurationError):
    default_message = "Project preset '{preset_name}' not found"


class ProjectConfigurationFilesNotFound(ConfigurationError):
    default_message = "Preset configuration files not found in path: '{preset_dir}'"


class ConfigValueTypeError(ConfigurationError):
    default_message = "Unsupported configuration value type '{type}' for key '{key}'"


class ConfigDeserializationError(ConfigurationError):
    default_message = "Unable to deserialize configuration from the environment variable '{var_name}'"


class HookError(Error):
    pass


class InvalidCallbackError(HookError):
    default_message = "Invalid callback '{callback}' provided for '{hook_name}' hook"


class SearchPathsNotDefinedError(HookError):
    default_message = "Hook search paths are not provided. " \
              "Check if 'BD_HOOKPATH' environment variable exists"


class HookLoadingError(HookError):
    default_message = "Hook '{path}' failed to load. {exc_msg}"


class HookRegistrationError(HookError):
    default_message = "Failed to register hook from 'path'. {exc_msg}"


class CallbackExecutionError(HookError):
    default_message = "Failed to execute callback '{callback}' for hook '{hook_name}'. {exc_msg}"


class HookNotFoundError(HookError):
    default_message = "Unable to find a hook '{hook_name}'"


class HookCallbackDeadError(HookError):
    default_message = "All callback owners for hook '{hook_name}' are dead"

