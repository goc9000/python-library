import shutil
import subprocess

from typing import Optional, Union, Any

from ..StayAwakeBackend import StayAwakeBackend


class GnomeSessionInhibitCmdBackend(StayAwakeBackend):
    """
    Linux backend that makes use of the `gnome-session-inhibit` utility, if available.

    It would be more elegant to access DBus directly, of course, but doing it this way helps us avoid needing to install
    any extra Python dependencies.
    """

    @classmethod
    def description(cls) -> str:
        return "Linux backend using the 'gnome-session-inhibit' command"

    @classmethod
    def platform(cls) -> Optional[str]:
        return 'linux'

    @classmethod
    def check_available(cls) -> Union[bool, str]:
        if not shutil.which('gnome-session-inhibit'):
            return "Command 'gnome-session-inhibit' not available"

        return True

    def disable_sleep(self, reason: Optional[str] = None, who: Optional[str] = None) -> Any:
        args = [
            'gnome-session-inhibit',
            '--inhibit', 'suspend',
            '--inhibit', 'idle',
            '--inhibit-only'
        ]

        if reason is not None:
            args.extend(['--reason', reason])
        if who is not None:
            args.extend(['--app-id', who])

        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # TODO: could check here that the process is actually waiting and has not exited immediately

        return process

    def restore_sleep(self, token: Any) -> None:
        token.terminate()
        token.wait()
