from enum import Enum


class BasicErrorCode(Enum):
    INTERNAL_ERROR = 'internal-error'
    REQUEST_NOT_JSON = 'request-not-json'
    REQUEST_TOO_LARGE = 'request-too-large'
    SHUTTING_DOWN = 'shutting-down'


class BasicError(Exception):
    _code: BasicErrorCode

    def __init__(self, code: BasicErrorCode, message: str):
        self._code = code
        super().__init__(message)

    @property
    def code(self) -> BasicErrorCode:
        return self._code


class InternalError(BasicError):
    def __init__(self):
        super().__init__(BasicErrorCode.INTERNAL_ERROR, "Internal error")


class RequestNotJSONError(BasicError):
    def __init__(self):
        super().__init__(BasicErrorCode.REQUEST_NOT_JSON, "Request is not valid one-line JSON")


class RequestTooLargeError(BasicError):
    def __init__(self):
        super().__init__(BasicErrorCode.REQUEST_TOO_LARGE, "Request too large")


class DaemonShuttingDownError(BasicError):
    def __init__(self):
        super().__init__(BasicErrorCode.SHUTTING_DOWN, "Daemon is shutting down")
