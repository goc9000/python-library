from enum import Enum


class BasicErrorCode(Enum):
    INTERNAL_ERROR = 'internal-error'
    REQUEST_NOT_JSON = 'request-not-json'
    REQUEST_TOO_LARGE = 'request-too-large'
    SHUTTING_DOWN = 'shutting-down'
