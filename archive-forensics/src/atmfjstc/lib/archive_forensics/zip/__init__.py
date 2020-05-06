import zipfile

from enum import IntEnum
from typing import Set, Union


class ZipHostOS(IntEnum):
    FAT = 0
    AMIGA = 1
    OPEN_VMS = 2
    UNIX = 3
    VM_CMS = 4
    ATARI_TOS = 5
    HPFS = 6
    MACINTOSH = 7
    Z_SYSTEM = 8
    CPM = 9
    TOPS_20 = 10  # also used for Windows by PKWARE, allegedly?
    NTFS = 11
    SMS_QDOS = 12
    RISC_OS = 13
    VFAT = 14
    MVS = 15
    BEOS = 16
    TANDEM = 17
    THEOS = 18
    OSX = 19
    ATHEOS = 30


WIN_COMPATIBLE_ZIP_OSES: Set[ZipHostOS] = {ZipHostOS.FAT, ZipHostOS.HPFS, ZipHostOS.NTFS, ZipHostOS.VFAT}
"""Operating systems for which the ZIP file attributes are in DOS/Windows-compatible format"""

POSIX_COMPATIBLE_ZIP_OSES: Set[ZipHostOS] = {ZipHostOS.UNIX, ZipHostOS.BEOS, ZipHostOS.OSX}
"""Operating systems for which the ZIP file attributes are in POSIX-compatible format"""


def is_windows_compatible_zip_os(host_os: Union[ZipHostOS, int]) -> bool:
    return host_os in WIN_COMPATIBLE_ZIP_OSES


def is_posix_compatible_zip_os(host_os: Union[ZipHostOS, int]) -> bool:
    return host_os in POSIX_COMPATIBLE_ZIP_OSES


class ZipCompressionMethod(IntEnum):
    STORE = 0
    SHRINK = 1
    REDUCE1 = 2
    REDUCE2 = 3
    REDUCE3 = 4
    REDUCE4 = 5
    IMPLODE = 6
    TOKENIZE = 7
    DEFLATE = 8
    DEFLATE64 = 9
    DCL_IMPLODE = 10
    BZIP2 = 12


def decompress_now(data: bytes, compress_type: Union[int, ZipCompressionMethod]) -> bytes:
    """
    Decompress a small amount of data according to the ZIP compression type.
    """
    if compress_type == ZipCompressionMethod.STORE:
        return data

    # KLUDGE
    decompressor = zipfile._get_decompressor(compress_type)
    return decompressor.decompress(data)
