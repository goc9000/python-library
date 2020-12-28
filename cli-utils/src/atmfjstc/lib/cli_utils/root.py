import os

from pathlib import Path


def is_root() -> bool:
    """
    Checks whether the current user is root (or, on Windows, an administrator).
    """

    if os.name == 'nt':
        try:
            _dummy = list((Path(os.environ.get('SystemRoot', 'C:\\Windows')) / 'Temp').iterdir())
            return True
        except OSError:
            return False
    else:
        return ('SUDO_USER' in os.environ) and (os.geteuid() == 0)
