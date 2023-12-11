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
    def platform(cls) -> Optional[str]:
        """
        Gets a specifier for the platform to which this backend is applicable (as reported by sys.platform()). This can
        be used to quickly filter out backends that cannot possibly be available on the current system.

        Returns:
            A platform string like 'win32', 'linux', 'darwin' etc., or None if the backend is potentially applicable to
            multiple platforms.
        """
        return None

    @classmethod
    def priority(cls) -> int:
        """
        Gets the priority for the backend. A backend with a higher priority will be selected over a lesser priority one
        if both are available.

        Returns:
            A priority number (higher means more preferred)
        """
        return 0

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
