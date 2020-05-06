from enum import IntFlag

from atmfjstc.lib.iso_timestamp import ISOTimestamp, iso_from_unix_time_nanos


class WindowsFileAttributes(IntFlag):
    READ_ONLY = 1 << 0
    HIDDEN = 1 << 1
    SYSTEM = 1 << 2
    DIRECTORY = 1 << 4
    NEEDS_ARCHIVING = 1 << 5
    DEVICE = 1 << 6
    NORMAL = 1 << 7
    TEMPORARY = 1 << 8
    SPARSE_FILE = 1 << 9
    REPARSE_POINT = 1 << 10
    COMPRESSED = 1 << 11
    OFFLINE = 1 << 12
    NOT_CONTENT_INDEXED = 1 << 13
    ENCRYPTED = 1 << 14
    INTEGRITY_STREAM = 1 << 15
    VIRTUAL = 1 << 16
    NO_SCRUB_DATA = 1 << 17


def iso_from_ntfs_time(ntfs_time: int) -> ISOTimestamp:
    """
    Converts from an NTFS timestamp, which is defined as the (integer) number of 100 nanosecond increments since the
    Windows NT epoch "1601-01-01 00:00:00 UTC".

    The resulting timestamp is always aware and referenced to UTC.
    """

    # Algorithm lifted from rarfile.py
    return iso_from_unix_time_nanos(ntfs_time * 100 - 11644473600000000000)
