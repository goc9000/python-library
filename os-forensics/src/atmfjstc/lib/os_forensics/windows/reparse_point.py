from abc import ABCMeta
from typing import Union, NamedTuple, Optional
from enum import IntEnum, IntFlag
from dataclasses import dataclass

from atmfjstc.lib.binary_utils.BinaryReader import BinaryReader, BinaryReaderFormatError


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


@dataclass(frozen=True)
class MicrosoftReparsePointData:
    """
    Parsed content corresponding to a REPARSE_DATA_BUFFER structure, used for e.g. symlinks, mountpoints, and junctions.
    """
    tag: Union[NTReparsePointTag, int]
    content: 'MicrosoftReparsePointContent'


class MicrosoftReparsePointContent(metaclass=ABCMeta):
    pass


@dataclass(frozen=True)
class UnknownReparsePointContent(MicrosoftReparsePointContent):
    raw_data: bytes


class NTSymlinkFlags(IntFlag):
    RELATIVE = 1 << 0


@dataclass(frozen=True)
class SymlinkReparsePointContent(MicrosoftReparsePointContent):
    substitute_name: str
    print_name: Optional[str]
    flags: NTSymlinkFlags


@dataclass(frozen=True)
class MountPointReparsePointContent(MicrosoftReparsePointContent):
    substitute_name: str
    print_name: Optional[str]


def analyze_nt_reparse_point_tag(tag: Union[NTReparsePointTag, int]) -> NTReparsePointTagAnalysis:
    return NTReparsePointTagAnalysis(
        is_microsoft=bool((tag >> 31) & 1),
        is_surrogate=bool((tag >> 29) & 1),
        value=tag & 0xffff,
        reserved=(tag >> 16) & 0x0fff,
        reserved28=(tag >> 28) & 1,
        reserved30=(tag >> 30) & 1,
    )


def decode_microsoft_reparse_point_data(raw_data: Union[bytes, BinaryReader]) -> MicrosoftReparsePointData:
    reader = raw_data if isinstance(raw_data, BinaryReader) else BinaryReader(raw_data, big_endian=False)

    tag = reader.read_uint32("reparse tag")
    data_len = reader.read_uint16("reparse data length")
    reserved = reader.read_uint16("reserved")
    reparse_data = reader.read_amount(data_len, "raw reparse point data")

    try:
        tag = NTReparsePointTag(tag)
    except Exception:
        pass

    if tag not in {NTReparsePointTag.SYMLINK, NTReparsePointTag.MOUNT_POINT}:
        return MicrosoftReparsePointData(
            tag=tag,
            content=UnknownReparsePointContent(raw_data=reparse_data),
        )

    reader = BinaryReader(reparse_data, big_endian=False)

    substitute_name_offset = reader.read_uint16("substitute name offset")
    substitute_name_length = reader.read_uint16("substitute name length")
    print_name_offset = reader.read_uint16("print name offset")
    print_name_length = reader.read_uint16("print name length")

    if tag == NTReparsePointTag.SYMLINK:
        link_flags = NTSymlinkFlags(reader.read_uint32())

    raw_path_data = reader.read_remainder()

    substitute_name = _extract_name_in_raw_path(
        raw_path_data, substitute_name_offset, substitute_name_length, "substitute name"
    )
    print_name = _extract_name_in_raw_path(raw_path_data, print_name_offset, print_name_length, "print name")

    return MicrosoftReparsePointData(
        tag=tag,
        content=SymlinkReparsePointContent(
            substitute_name=substitute_name,
            print_name=print_name if print_name != '' else None,
            flags=link_flags,
        ) if tag == NTReparsePointTag.SYMLINK else MountPointReparsePointContent(
            substitute_name=substitute_name,
            print_name=print_name if print_name != '' else None,
        ),
    )


def _extract_name_in_raw_path(raw_path_data: bytes, offset: int, length: int, meaning: str) -> str:
    if offset > len(raw_path_data):
        raise BinaryReaderFormatError(
            f"Offset for {meaning} is beyond the length of the data: {offset} > {len(raw_path_data)}"
        )
    if offset + length > len(raw_path_data):
        raise BinaryReaderFormatError(
            f"Tried to read {length} bytes for {meaning}, but only {len(raw_path_data) - offset} were found"
        )

    raw_str = raw_path_data[offset:offset + length]

    return raw_str.decode('utf-16')
