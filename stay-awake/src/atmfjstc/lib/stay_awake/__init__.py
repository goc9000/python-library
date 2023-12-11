"""
Utility for keeping the system/screen awake, using the OS-specific API for doing so.

This is useful for when we have an application that accepts input in a way that is not recognized by the operating
system as being user activity, e.g. MIDI keyboard or controller.

Caution: this module is not thread-safe.

TODO: currently only the OS X backend is implemented.
"""

__version__ = '0.1.3'


import sys

from typing import Optional, ContextManager
from contextlib import contextmanager

from ._backends import ALL_BACKENDS
from ._backends.StayAwakeBackend import StayAwakeBackend


_backend: Optional[StayAwakeBackend] = None
_backend_selected: bool = False


def disable_sleep(reason: Optional[str] = None) -> None:
    """
    Keeps the system from sleeping, until `restore_sleep()` is called.

    The function can be called multiple times; in that case, `restore_sleep()` must also be called that many times
    before the system can sleep again.

    Args:
        reason: Text describing the reason why the system is being kept awake (some OSes allow an admin to see this)
    """
    backend = _get_backend()

    if backend is not None:
        backend.disable_sleep(reason)


def restore_sleep() -> None:
    """
    Ends the no-sleep period initiated by a previous `disable_sleep` call.
    """
    backend = _get_backend()

    if backend is not None:
        backend.restore_sleep()


@contextmanager
def no_sleep(reason: Optional[str] = None) -> ContextManager[None]:
    """
    Context manager for keeping the system awake while it is in effect.

    Args:
        reason: Text describing the reason why the system is being kept awake (some OSes allow an admin to see this)
    """

    disable_sleep(reason)

    try:
        yield
    finally:
        restore_sleep()


def is_preventing_sleep() -> bool:
    """
    Checks whether we are in a no-sleep period initiated by this module.

    Note: this does not check whether some other application is preventing system sleep.

    Returns:
        True if sleep is currently being prevented by this module.
    """
    backend = _get_backend()

    return backend.is_preventing_sleep() if backend is not None else False


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
