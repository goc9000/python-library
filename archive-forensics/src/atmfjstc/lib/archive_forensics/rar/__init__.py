from enum import IntEnum, IntFlag
from typing import Set, Union


class RarHostOS(IntEnum):
    DOS = 0
    OS2 = 1
    WINDOWS = 2
    UNIX = 3
    MACOS = 4
    BEOS = 5


WIN_COMPATIBLE_RAR_OSES: Set[RarHostOS] = {RarHostOS.DOS, RarHostOS.OS2, RarHostOS.WINDOWS}
"""Operating systems for which the RAR file attributes are in DOS/Windows-compatible format"""

POSIX_COMPATIBLE_RAR_OSES: Set[RarHostOS] = {RarHostOS.UNIX, RarHostOS.MACOS, RarHostOS.BEOS}
"""Operating systems for which the RAR file attributes are in POSIX-compatible format"""


def is_windows_compatible_rar_os(host_os: Union[RarHostOS, int]) -> bool:
    return host_os in WIN_COMPATIBLE_RAR_OSES


def is_posix_compatible_rar_os(host_os: Union[RarHostOS, int]) -> bool:
    return host_os in POSIX_COMPATIBLE_RAR_OSES


class RarCompressionMethod(IntEnum):
    STORE = 48
    M1 = 49
    M2 = 50
    M3 = 51
    M4 = 52
    M5 = 53


class RarRedirType(IntEnum):
    UNIX_SYMLINK = 1
    WINDOWS_SYMLINK = 2
    WINDOWS_JUNCTION = 3
    HARDLINK = 4
    FILE_COPY = 5


class RarRedirFlags(IntFlag):
    TARGET_IS_DIRECTORY = 1 << 0


class RarFileVersionFlags(IntFlag):
    CLEAR = 0  # No flags are known to be defined
