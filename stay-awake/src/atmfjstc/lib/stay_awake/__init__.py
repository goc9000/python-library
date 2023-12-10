"""
Utility for keeping the system/screen awake, using the OS-specific API for doing so.

This is useful for when we have an application that accepts input in a way that is not recognized by the operating
system as being user activity, e.g. MIDI keyboard or controller.

Caution: this module is not thread-safe.

TODO: currently only the OS X backend is implemented.
"""

__version__ = '0.1.2'


import sys
import platform

from typing import Optional, ContextManager
from distutils.version import LooseVersion as V
from contextlib import contextmanager

from atmfjstc.lib.stay_awake._backends.StayAwakeBackend import StayAwakeBackend


_backend: StayAwakeBackend


def disable_sleep(reason: Optional[str] = None) -> None:
    """
    Keeps the system from sleeping, until `restore_sleep()` is called.

    The function can be called multiple times; in that case, `restore_sleep()` must also be called that many times
    before the system can sleep again.

    Args:
        reason: Text describing the reason why the system is being kept awake (some OSes allow an admin to see this)
    """
    _backend.disable_sleep(reason)


def restore_sleep() -> None:
    """
    Ends the no-sleep period initiated by a previous `disable_sleep` call.
    """
    _backend.restore_sleep()


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
    return _backend.is_preventing_sleep()


def is_prevent_sleep_supported() -> bool:
    """
    Checks whether this module can prevent sleep on this system.
    Returns:
        True if sleep prevention is supported.
    """
    return _backend.is_prevent_sleep_supported()


def _init_backend() -> None:
    global _backend

    if sys.platform == 'darwin' and not (V(platform.mac_ver()[0]) < V('10.9')):
        from atmfjstc.lib.stay_awake._backends.StayAwakeOsXBackend import StayAwakeOsXBackend

        _backend = StayAwakeOsXBackend()
    else:
        from atmfjstc.lib.stay_awake._backends.StayAwakeNopBackend import StayAwakeNopBackend

        _backend = StayAwakeNopBackend()


_init_backend()
