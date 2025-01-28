from typing import Union, NamedTuple
from enum import IntEnum


class NTReparsePointTag(IntEnum):
    MOUNT_POINT      = 0xA0000003
    HSM              = 0xC0000004
    DRIVE_EXTENDER   = 0x80000005
    HSM2             = 0x80000006
    SIS              = 0x80000007
    WIM              = 0x80000008
    CSV              = 0x80000009
    DFS              = 0x8000000A
    FILTER_MANAGER   = 0x8000000B
    SYMLINK          = 0xA000000C
    IIS_CACHE        = 0xA0000010
    DFSR             = 0x80000012
    DEDUP            = 0x80000013
    NFS              = 0x80000014
    FILE_PLACEHOLDER = 0x80000015
    WOF              = 0x80000017
    WCI              = 0x80000018
    WCI_1            = 0x90001018
    GLOBAL_REPARSE   = 0xA0000019
    CLOUD            = 0x9000001A
    CLOUD_1          = 0x9000101A
    CLOUD_2          = 0x9000201A
    CLOUD_3          = 0x9000301A
    CLOUD_4          = 0x9000401A
    CLOUD_5          = 0x9000501A
    CLOUD_6          = 0x9000601A
    CLOUD_7          = 0x9000701A
    CLOUD_8          = 0x9000801A
    CLOUD_9          = 0x9000901A
    CLOUD_A          = 0x9000A01A
    CLOUD_B          = 0x9000B01A
    CLOUD_C          = 0x9000C01A
    CLOUD_D          = 0x9000D01A
    CLOUD_E          = 0x9000E01A
    CLOUD_F          = 0x9000F01A
    APPEXECLINK      = 0x8000001B
    GVFS             = 0x9000001C
    STORAGE_SYNC     = 0x8000001E
    WCI_TOMBSTONE    = 0xA000001F
    UNHANDLED        = 0x80000020
    ONEDRIVE         = 0x80000021
    GVFS_TOMBSTONE   = 0xA0000022


class NTReparsePointTagAnalysis(NamedTuple):
    is_microsoft: bool
    is_surrogate: bool
    value: int
    reserved: int
    reserved28: int
    reserved30: int


def analyze_nt_reparse_point_tag(tag: Union[NTReparsePointTag, int]) -> NTReparsePointTagAnalysis:
    return NTReparsePointTagAnalysis(
        is_microsoft=bool((tag >> 31) & 1),
        is_surrogate=bool((tag >> 29) & 1),
        value=tag & 0xffff,
        reserved=(tag >> 16) & 0x0fff,
        reserved28=(tag >> 28) & 1,
        reserved30=(tag >> 30) & 1,
    )
