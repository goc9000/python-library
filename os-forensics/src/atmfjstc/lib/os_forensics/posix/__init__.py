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

PosixDeviceIDKDevTFormat = NewType('PosixDeviceIDKDevTFormat', int)
"""
A device ID represented as an int equal to (major_id << MINOR_BITS) + minor_id (as in the C type ``kdev_t``). You need
to know the value of MINOR_BITS (system dependent) to be able to decode it.
"""

INodeNo = NewType('INodeNo', int)


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
    return PosixPermissionsString(stat.filemode(permissions)[1:])


def posix_permissions_string_to_num(permissions: PosixPermissionsString) -> PosixNumericPermissions:
    result = _STR_TO_NUM_CONVERSION_CACHE.get(permissions)

    if result is not None:
        return result

    if len(_STR_TO_NUM_CONVERSION_CACHE) == 0:
        for bits in range(0, 1 << 12):
            as_num = PosixNumericPermissions(bits)
            as_str = posix_permissions_num_to_string(as_num)
            _STR_TO_NUM_CONVERSION_CACHE[as_str] = as_num

    # Either the cache was not built, or the string was bad. Run the slow path to detect the exact error.

    return _posix_permissions_string_to_num_slow(permissions)


_STR_TO_NUM_CONVERSION_CACHE = {}


def _posix_permissions_string_to_num_slow(permissions: PosixPermissionsString) -> PosixNumericPermissions:
    if len(permissions) != 9:
        raise ValueError("POSIX permissions string must be exactly 9 characters long")

    result = PosixNumericPermissions(0)

    for index, char in enumerate(permissions):
        if char != '-':
            part = _STR_TO_NUM_CONVERSION_LOOKUP.get((index, char))

            if part is None:
                raise ValueError(f"Invalid character '{char}' at index #{index} in POSIX permissions string")

            result |= part

    return result


_STR_TO_NUM_CONVERSION_LOOKUP = {
    (0, 'r'): PosixNumericPermissions.OWNER_READ,
    (1, 'w'): PosixNumericPermissions.OWNER_WRITE,
    (2, 'x'): PosixNumericPermissions.OWNER_EXEC,
    (2, 's'): PosixNumericPermissions.SET_UID | PosixNumericPermissions.OWNER_EXEC,
    (2, 'S'): PosixNumericPermissions.SET_UID,
    (3, 'r'): PosixNumericPermissions.GROUP_READ,
    (4, 'w'): PosixNumericPermissions.GROUP_WRITE,
    (5, 'x'): PosixNumericPermissions.GROUP_EXEC,
    (5, 's'): PosixNumericPermissions.SET_GID | PosixNumericPermissions.GROUP_EXEC,
    (5, 'S'): PosixNumericPermissions.SET_GID,
    (6, 'r'): PosixNumericPermissions.OTHERS_READ,
    (7, 'w'): PosixNumericPermissions.OTHERS_WRITE,
    (8, 'x'): PosixNumericPermissions.OTHERS_EXEC,
    (8, 't'): PosixNumericPermissions.STICKY | PosixNumericPermissions.OTHERS_EXEC,
    (8, 'T'): PosixNumericPermissions.STICKY,
}
