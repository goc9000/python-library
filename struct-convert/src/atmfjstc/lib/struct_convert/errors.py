class ConvertStructCompileError(Exception):
    """
    Base class for all exceptions related to setting up a struct converter incorrectly.
    """


class ConvertStructRuntimeError(Exception):
    """
    Base class for all exceptions thrown when a struct converter encounters bad data at runtime.
    """


class ConvertStructMissingRequiredFieldError(ConvertStructRuntimeError):
    field = None

    def __init__(self, field):
        super().__init__(f"Missing required field '{field}'")
        self.field = field


class ConvertStructWrongSourceTypeError(ConvertStructRuntimeError):
    pass
