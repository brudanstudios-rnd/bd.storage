class BDException(Exception):
    message = "Generic runtime error."


class BDPipelineNotActivatedError(BDException):

    message = ("Pipeline is not activated yet. "
               "Check if 'BD_PIPELINE_DIR' environment variable exists")

    def __init__(self):
        super(BDPipelineNotActivatedError, self).__init__(self.message)


class BDMandatoryKeyNotFound(BDException):

    message = "Mandatory key '{}' could not be found in any of the configuration files"

    def __init__(self, key):
        super(BDMandatoryKeyNotFound, self).__init__(self.message.format(key))


class BDFilesystemPathNotFound(BDException):
    
    message = "Filesystem path '{}' not found"
    
    def __init__(self, path):
        super(BDFilesystemPathNotFound, self).__init__(self.message.format(str(path)))


class BDFailedConfigParsing(BDException):

    message = "Failed to parse configuration: {}"

    def __init__(self, message):
        super(BDFailedConfigParsing, self).__init__(self.message.format(message))


class BDProjectConfigurationNotFound(BDException):

    message = "Project configuration '{}' not found"

    def __init__(self, config_name):
        super(BDProjectConfigurationNotFound, self).__init__(self.message.format(config_name))
        
        
class BDUnableToOverwrite(BDException):
    
    message = "Unable to overwrite '{}'"
    
    def __init__(self, path):
        super(BDUnableToOverwrite, self).__init__(self.message.format(path))