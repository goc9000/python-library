from typing import Optional, Union

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

    @classmethod
    @abstractmethod
    def check_available(cls) -> Union[bool, str]:
        """
        Checks if the backend is applicable to the current system.

        Returns:
            True if the backend is applicable. If not, either a string (detailing the reason), or False if no
            explanation is provided.

        Raises:
            Exception: The method may also throw any exception to indicate that the backend is not available
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
