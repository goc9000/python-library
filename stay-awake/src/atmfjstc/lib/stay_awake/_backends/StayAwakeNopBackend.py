from typing import Optional

from atmfjstc.lib.stay_awake._backends.StayAwakeBackend import StayAwakeBackend


class StayAwakeNopBackend(StayAwakeBackend):
    """
    No-operation backend for operating systems not supported by this module.
    """

    def disable_sleep(self, reason: Optional[str] = None) -> None:
        pass

    def restore_sleep(self) -> None:
        pass

    def is_preventing_sleep(self) -> bool:
        return False

    def is_prevent_sleep_supported(self) -> bool:
        return False
