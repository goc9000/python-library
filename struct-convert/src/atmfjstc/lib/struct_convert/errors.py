from typing import Type


class ConvertStructCompileError(Exception):
    """
    Base class for all exceptions related to setting up a struct converter incorrectly.
    """


class ConvertStructRuntimeError(Exception):
    """
    Base class for all exceptions thrown when a struct converter encounters bad data at runtime.
    """


class ConvertStructMissingRequiredFieldError(ConvertStructRuntimeError):
    field: str

    def __init__(self, field: str):
        super().__init__(f"Missing required field '{field}'")

        self.field = field


class ConvertStructWrongSourceTypeError(ConvertStructRuntimeError):
    expected_type: Type
    actual_type: Type

    def __init__(self, expected_type: Type, actual_type: Type):
        super().__init__(f"Expected source of type '{expected_type.__name__}', got '{actual_type.__name__}'")

        self.expected_type = expected_type
        self.actual_type = actual_type


class ConvertStructWrongDestinationTypeError(ConvertStructRuntimeError):
    expected_type: Type
    actual_type: Type

    def __init__(self, expected_type: Type, actual_type: Type):
        super().__init__(f"Expected destination of type '{expected_type.__name__}', got '{actual_type.__name__}'")

        self.expected_type = expected_type
        self.actual_type = actual_type
