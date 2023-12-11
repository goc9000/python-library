from typing import Type

from .StayAwakeBackend import StayAwakeBackend
from .mac.OsXBackend import OsXBackend


ALL_BACKENDS: list[Type[StayAwakeBackend]] = [
    OsXBackend,
]
