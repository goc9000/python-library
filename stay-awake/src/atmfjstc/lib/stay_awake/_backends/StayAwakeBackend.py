from typing import Optional

from abc import ABCMeta, abstractmethod


class StayAwakeBackend(metaclass=ABCMeta):
    @abstractmethod
    def disable_sleep(self, reason: Optional[str] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def restore_sleep(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_preventing_sleep(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_prevent_sleep_supported(self) -> bool:
        raise NotImplementedError
