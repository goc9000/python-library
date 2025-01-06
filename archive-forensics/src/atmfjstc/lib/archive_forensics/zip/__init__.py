import zipfile

from enum import IntEnum, IntFlag
from typing import Set, Union


class ZipEntryFlags(IntFlag):
    ENCRYPTED = 1 << 0
    IMPLODE_8K_DICTIONARY = 1 << 1
    IMPLODE_3_SHANNON_TREES = 1 << 2
    DEFLATE_MAX_COMPRESSION = 1 << 1
    DEFLATE_FAST_COMPRESSION = 1 << 2
    DEFLATE_SUPERFAST_COMPRESSION = (1 << 1) | (1 << 2)
    LZMA_EOS_MARKER_USED = 1 << 1
    DEFERRED_CRC32 = 1 << 3
    ENHANCED_DEFLATE = 1 << 4
    PATCHED_DATA = 1 << 5
    STRONG_ENCRYPTION = 1 << 6
    UTF8 = 1 << 11
    ENHANCED_COMPRESSION = 1 << 12
    LOCAL_HEADER_MASKED = 1 << 13


class ZipInternalFileAttributes(IntFlag):
    LIKELY_TEXT_FILE = 1 << 0


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
    LZMA = 14
    ZOS_CMPSC = 16
    IBM_TERSE_NEW = 18
    IBM_LZ77 = 19
    ZSTANDARD_OLD = 20
    ZSTANDARD = 93
    MP3 = 94
    XZ = 95
    JPEG_VARIANT = 96
    WAVPACK = 97
    PPMD = 98
    AE_X_ENCRYPTION = 99


def decompress_now(data: bytes, compress_type: Union[int, ZipCompressionMethod]) -> bytes:
    """
    Decompress a small amount of data according to the ZIP compression type.
    """
    if compress_type == ZipCompressionMethod.STORE:
        return data

    # KLUDGE
    decompressor = zipfile._get_decompressor(compress_type)
    return decompressor.decompress(data)
