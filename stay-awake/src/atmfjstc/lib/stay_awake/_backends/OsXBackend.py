import ctypes
import ctypes.util

from typing import Optional, Union, List
from enum import IntFlag

from .StayAwakeBackend import StayAwakeBackend


class OsXBackend(StayAwakeBackend):
    """
    OS X backend. Based on code from the `app_nope` module at https://github.com/minrk/appnope

    We could use PyObjC etc., but we need this to be as lightweight as possible.
    """

    _objc: 'MiniObjCInterface'
    _layers: List[int]

    def __init__(self):
        self._objc = MiniObjCInterface()
        self._layers = []

    @classmethod
    def description(cls) -> str:
        return "Activity-based backend for Mac OS X and above"

    def disable_sleep(self, reason: Optional[str] = None) -> None:
        reason = self._objc.msg(self._objc.cls('NSString'), 'stringWithUTF8String:', (reason or '').encode('utf-8'))
        process_info = self._objc.msg(self._objc.cls('NSProcessInfo'), 'processInfo')

        activity = self._objc.msg(
            process_info, 'beginActivityWithOptions:reason:',
            ctypes.c_uint64(NSActivityOptions.UserInitiated | NSActivityOptions.IdleDisplaySleepDisabled),
            ctypes.c_void_p(reason)
        )
        assert activity is not None, 'Could not create activity?!'

        self._layers.append(activity)

    def restore_sleep(self) -> None:
        if len(self._layers) == 0:
            return

        activity = self._layers.pop()

        process_info = self._objc.msg(self._objc.cls('NSProcessInfo'), 'processInfo')

        self._objc.msg(process_info, 'endActivity:', ctypes.c_void_p(activity))

    def is_preventing_sleep(self) -> bool:
        return len(self._layers) > 0


class MiniObjCInterface:
    _objc = None
    _lib_foundation = None

    def __init__(self):
        def must_load(lib_name):
            path = ctypes.util.find_library(lib_name)
            assert path is not None, f"'{lib_name}' library not found?!"

            return ctypes.cdll.LoadLibrary(path)

        objc = must_load('objc')
        self._lib_foundation = must_load('Foundation')

        objc.objc_getClass.restype = ctypes.c_void_p

        objc.sel_registerName.restype = ctypes.c_void_p

        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        self._objc = objc

    def cls(self, class_name: str) -> int:
        """Get an ObjC class by name"""
        result = self._objc.objc_getClass(class_name.encode('utf-8'))

        assert result is not None, f"Class not found: {class_name}"

        return result

    def sel(self, selector_name: str) -> int:
        """create a selector name (for methods)"""
        return self._objc.sel_registerName(selector_name.encode('utf-8'))

    def msg(self, instance: int, selector: Union[int, str], *args):
        if isinstance(selector, str):
            selector = self.sel(selector)

        return self._objc.objc_msgSend(instance, selector, *args)


class NSActivityOptions(IntFlag):
    IdleDisplaySleepDisabled     = 0x10000000000
    IdleSystemSleepDisabled      = 0x00000100000
    SuddenTerminationDisabled    = 0x00000004000
    AutomaticTerminationDisabled = 0x00000008000
    UserInitiated                = 0x00000FFFFFF | IdleSystemSleepDisabled
    Background                   = 0x000000000FF
    LatencyCritical              = 0x0FF00000000

    UserInitiatedAllowingIdleSystemSleep = UserInitiated & ~IdleSystemSleepDisabled
