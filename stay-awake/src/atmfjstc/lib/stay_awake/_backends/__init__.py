from typing import Type

from .StayAwakeBackend import StayAwakeBackend
from .linux.GnomeSessionInhibitCmdBackend import GnomeSessionInhibitCmdBackend
from .mac.OsXBackend import OsXBackend


ALL_BACKENDS: list[Type[StayAwakeBackend]] = [
    GnomeSessionInhibitCmdBackend,
    OsXBackend,
]
