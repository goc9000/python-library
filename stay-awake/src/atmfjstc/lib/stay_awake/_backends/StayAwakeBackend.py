from typing import Optional

from abc import ABCMeta, abstractmethod


class StayAwakeBackend(metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def description(cls) -> str:
        """
        Gets a short description of the backend (mostly for debug purposes)

        Returns:
            A short text describing the backend
        """
        raise NotImplementedError

    @abstractmethod
    def disable_sleep(self, reason: Optional[str] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def restore_sleep(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_preventing_sleep(self) -> bool:
        raise NotImplementedError
