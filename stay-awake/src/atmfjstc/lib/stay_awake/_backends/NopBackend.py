from typing import Optional

from .StayAwakeBackend import StayAwakeBackend


class NopBackend(StayAwakeBackend):
    """
    No-operation backend for operating systems not supported by this module.
    """

    def disable_sleep(self, reason: Optional[str] = None) -> None:
        pass

    def restore_sleep(self) -> None:
        pass

    def is_preventing_sleep(self) -> bool:
        return False
