"""
Utility for keeping the system/screen awake, using the OS-specific API for doing so.

This is useful for when we have an application that accepts input in a way that is not recognized by the operating
system as being user activity, e.g. MIDI keyboard or controller.

Caution: this module is not thread-safe.

TODO: currently only a limited set of backends is implemented.
"""

__version__ = '0.3.0'


import sys

from typing import Optional, ContextManager, Any
from contextlib import contextmanager
from dataclasses import dataclass

from ._backends import ALL_BACKENDS
from ._backends.StayAwakeBackend import StayAwakeBackend


_backend: Optional[StayAwakeBackend] = None
_backend_selected: bool = False


@dataclass(frozen=True, eq=False)
class WakeLock:
    token: Any
    "Internal token for re-enabling sleep"

    reason: Optional[str] = None
    "Text describing the reason why the system is being kept awake"

    who: Optional[str] = None
    "Text identifying the application that wants to keep the system awake"

    def end(self):
        """
        Ends the wake period associated with this lock.
        """
        _end_wake(self)


_wake_locks: list[WakeLock] = []


def disable_sleep(reason: Optional[str] = None, who: Optional[str] = None) -> WakeLock:
    """
    Keeps the system from sleeping from this point forward.

    Args:
        reason:
            Text describing the reason why the system is being kept awake. Whether this information is visible or
            easily accessible varies by system.
        who:
            Text identifying the application that wants to keep the system awake. Whether this information is visible or
            easily accessible varies by system.

    Returns:
        An object that can be used to end the wake period by calling its `.end()` method
    """
    backend = _get_backend()

    token = backend.disable_sleep(reason=reason, who=who) if backend is not None else None

    wake_lock = WakeLock(token=token, reason=reason, who=who)

    _wake_locks.append(wake_lock)

    return wake_lock


def restore_sleep() -> None:
    """
    Convenience method for ending the wake period initiated by the latest `disable_sleep` call.
    """
    if len(_wake_locks) == 0:
        return

    _end_wake(_wake_locks[-1])


def _end_wake(wake_lock: WakeLock):
    try:
        index = _wake_locks.index(wake_lock)
    except ValueError:
        return

    token = _wake_locks.pop(index).token

    backend = _get_backend()

    if backend is not None:
        backend.restore_sleep(token)


@contextmanager
def no_sleep(reason: Optional[str] = None) -> ContextManager[None]:
    """
    Context manager for keeping the system awake while it is in effect.

    Args:
        reason:
            Text describing the reason why the system is being kept awake. Whether this information is visible or
            easily accessible varies by system.
    """

    wake_lock = disable_sleep(reason)

    try:
        yield
    finally:
        wake_lock.end()


def is_preventing_sleep() -> bool:
    """
    Checks whether we are in a no-sleep period initiated by this module.

    Note: this does not check whether some other application is preventing system sleep.

    Returns:
        True if sleep is currently being prevented by this module.
    """

    return (_get_backend() is not None) and (len(_wake_locks) > 0)


def is_prevent_sleep_supported() -> bool:
    """
    Checks whether this module can prevent sleep on this system.
    Returns:
        True if sleep prevention is supported.
    """
    return _get_backend() is not None


def _get_backend() -> Optional[StayAwakeBackend]:
    global _backend
    global _backend_selected

    if not _backend_selected:
        _backend = _select_backend()
        _backend_selected = True

    return _backend


def _select_backend() -> Optional[StayAwakeBackend]:
    platform = sys.platform

    # First quickly filter by platform
    candidates = [candidate for candidate in ALL_BACKENDS if candidate.platform() in [None, platform]]

    for cls in sorted(candidates, key=lambda candidate: -candidate.priority()):
        try:
            result = cls.check_available()
        except Exception as e:
            result = str(e) if str(e) != '' else e.__class__.__name__

        if result is True:
            return cls()

        # TODO: maybe log the reason

    return None
