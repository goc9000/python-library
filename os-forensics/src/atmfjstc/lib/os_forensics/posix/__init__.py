import stat

from enum import IntEnum, IntFlag
from typing import NewType, Tuple


PosixMode = NewType('PosixMode', int)
PosixPermissionsString = NewType('PosixPermissionsString', str)

PosixUID = NewType('PosixUID', int)
PosixGID = NewType('PosixGID', int)

PosixDeviceIDMinor = NewType('PosixDeviceIDMinor', int)
PosixDeviceIDMajor = NewType('PosixDeviceIDMajor', int)
PosixDeviceID = NewType('PosixDeviceID', Tuple[PosixDeviceIDMajor, PosixDeviceIDMinor])


class PosixFileType(IntEnum):
    INVALID_0 = 0
    FIFO = 1
    CHAR_DEVICE = 2
    INVALID_3 = 3
    DIRECTORY = 4
    INVALID_5 = 5
    BLOCK_DEVICE = 6
    INVALID_7 = 7
    FILE = 8
    INVALID_9 = 9
    SYMLINK = 10
    INVALID_11 = 11
    SOCKET = 12
    DOOR = 13
    WHITEOUT = 14
    INVALID_15 = 15

    def is_valid(self):
        return not self.name.startswith('INVALID')


class PosixNumericPermissions(IntFlag):
    OTHERS_EXEC = 1 << 0
    OTHERS_WRITE = 1 << 1
    OTHERS_READ = 1 << 2
    GROUP_EXEC = 1 << 3
    GROUP_WRITE = 1 << 4
    GROUP_READ = 1 << 5
    OWNER_EXEC = 1 << 6
    OWNER_WRITE = 1 << 7
    OWNER_READ = 1 << 8
    STICKY = 1 << 9
    SET_GID = 1 << 10
    SET_UID = 1 << 11


class PosixFileFlags(IntFlag):
    NO_DUMP = 1 << 0
    IMMUTABLE = 1 << 1
    APPEND_ONLY = 1 << 2
    OPAQUE_IN_UNION = 1 << 3
    NO_UNLINK = 1 << 4
    COMPRESSED = 1 << 5
    TRACKED = 1 << 6
    SYSTEM = 1 << 7
    SPARSE_FILE = 1 << 8
    OFFLINE = 1 << 9
    REPARSE_POINT = 1 << 10
    NEEDS_ARCHIVING = 1 << 11
    READ_ONLY = 1 << 12
    HIDDEN = 1 << 15
    SU_ARCHIVED = 1 << 16
    SU_IMMUTABLE = 1 << 17
    SU_APPEND_ONLY = 1 << 18
    SU_NO_UNLINK = 1 << 20
    SNAPSHOT = 1 << 21


def split_posix_filemode(posix_mode: PosixMode) -> Tuple[PosixFileType, PosixNumericPermissions]:
    return extract_posix_file_type(posix_mode), extract_posix_permissions(posix_mode)


def extract_posix_file_type(posix_mode: PosixMode) -> PosixFileType:
    return PosixFileType(posix_mode >> 12)


def extract_posix_permissions(posix_mode: PosixMode) -> PosixNumericPermissions:
    return PosixNumericPermissions(posix_mode & 0xfff)


def posix_permissions_num_to_string(permissions: PosixNumericPermissions) -> PosixPermissionsString:
    return stat.filemode(permissions)[1:]
