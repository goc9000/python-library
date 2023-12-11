from typing import Type

from .StayAwakeBackend import StayAwakeBackend
from .OsXBackend import OsXBackend


ALL_BACKENDS: list[Type[StayAwakeBackend]] = [
    OsXBackend,
]
