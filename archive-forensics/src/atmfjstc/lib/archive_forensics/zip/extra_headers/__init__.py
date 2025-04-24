"""
Utilities for handling ZIP "extra data" fields
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Type, TypeVar

from atmfjstc.lib.iso_timestamp import ISOTimestamp
from atmfjstc.lib.os_forensics.windows.security import NTSecurityDescriptor
from atmfjstc.lib.os_forensics.posix import PosixUID, PosixGID, PosixDeviceID


def parse_zip_central_extra_data(field_bytes: bytes) -> List['ZipExtraHeader']:
    from ._parse import parse_zip_extra_data

    return parse_zip_extra_data(field_bytes, is_local=False)


def parse_zip_local_extra_data(field_bytes: bytes) -> List['ZipExtraHeader']:
    from ._parse import parse_zip_extra_data

    return parse_zip_extra_data(field_bytes, is_local=True)


@dataclass(frozen=True)
class ZipExtraHeader:
    magic: int
    is_local: bool
    interpretation_type: Optional[Type['ZipExtraHeaderInterpretation']] = None
    interpretation: Optional['ZipExtraHeaderInterpretation'] = None
    warnings: Tuple[str, ...] = ()
    unconsumed_data: bytes = b''

    @property
    def is_unrecognized(self) -> bool:
        return self.interpretation_type is None

    def description(self, short: bool = False) -> str:
        centrality_text = 'local' if self.is_local else 'central'
        type_text = f"0x{self.magic:04x}" if self.is_unrecognized else self.interpretation_type.__name__

        return f"{type_text} ({centrality_text})" \
            if short else f"ZIP {centrality_text} extra header of type {type_text}"


@dataclass(frozen=True)
class ZipExtraHeaderInterpretation:
    pass


@dataclass(frozen=True)
class ZXHZip64(ZipExtraHeaderInterpretation):
    sizes: Tuple[int, ...]
    disk_start_no: Optional[int]


TagT = TypeVar('TagT', bound='NTFSInfoTag')


@dataclass(frozen=True)
class ZXHPkWareNTFS(ZipExtraHeaderInterpretation):
    tags: Tuple['NTFSInfoTag', ...]
    reserved: int

    def get_single_tag(self, tag_type: Type[TagT]) -> Optional[TagT]:
        result = None

        for tag in self.tags:
            if isinstance(tag, tag_type):
                if result is not None:
                    raise ValueError(f"Found multiple {tag_type.__class__.__name__} tags")

                result = tag

        return result


@dataclass(frozen=True)
class NTFSInfoTag:
    pass


@dataclass(frozen=True)
class NTFSInfoTimestampsTag(NTFSInfoTag):
    mtime: ISOTimestamp
    atime: ISOTimestamp
    ctime: ISOTimestamp


@dataclass(frozen=True)
class NTFSInfoUnhandledTag(NTFSInfoTag):
    tag: int
    raw_data: bytes


@dataclass(frozen=True)
class ZXHPkWareUnix(ZipExtraHeaderInterpretation):
    atime: ISOTimestamp
    mtime: ISOTimestamp
    uid: PosixUID
    gid: PosixGID
    device: Optional[PosixDeviceID] = None
    link_target: Optional[bytes] = None


@dataclass(frozen=True)
class ZXHNTSecurityDescriptor(ZipExtraHeaderInterpretation):
    uncompressed_data_size: int
    data: Optional['NTSecurityDescriptorData']


@dataclass(frozen=True)
class NTSecurityDescriptorData:
    format_version: int
    compression_method: int


@dataclass(frozen=True)
class NTSecurityDescriptorDataCompressed(NTSecurityDescriptorData):
    compressed_data: bytes


@dataclass(frozen=True)
class NTSecurityDescriptorDataDecompressed(NTSecurityDescriptorData):
    raw_data: bytes


@dataclass(frozen=True)
class NTSecurityDescriptorDataV0(NTSecurityDescriptorDataDecompressed):
    format_version: int = field(default=0, init=False)
    descriptor: NTSecurityDescriptor


@dataclass(frozen=True)
class ZXHExtendedTimestamps(ZipExtraHeaderInterpretation):
    mtime: Optional[ISOTimestamp] = None
    atime: Optional[ISOTimestamp] = None
    ctime: Optional[ISOTimestamp] = None


@dataclass(frozen=True)
class ZXHInfoZipUnixV1(ZipExtraHeaderInterpretation):
    mtime: ISOTimestamp
    atime: ISOTimestamp
    uid: Optional[PosixUID] = None
    gid: Optional[PosixGID] = None


@dataclass(frozen=True)
class ZXHInfoZipUnicodeComment(ZipExtraHeaderInterpretation):
    data: Optional['IZUnicodeCommentData']


@dataclass(frozen=True)
class IZUnicodeCommentData:
    pass


@dataclass(frozen=True)
class IZUnicodeCommentDataUnsupported(IZUnicodeCommentData):
    format_version: int
    raw_data: bytes


@dataclass(frozen=True)
class IZUnicodeCommentDataV1(IZUnicodeCommentData):
    comment: str
    standard_comment_crc32: int


@dataclass(frozen=True)
class ZXHInfoZipUnicodePath(ZipExtraHeaderInterpretation):
    data: Optional['IZUnicodePathData']


@dataclass(frozen=True)
class IZUnicodePathData:
    pass


@dataclass(frozen=True)
class IZUnicodePathDataUnsupported(IZUnicodePathData):
    format_version: int
    raw_data: bytes


@dataclass(frozen=True)
class IZUnicodePathDataV1(IZUnicodePathData):
    path: str
    standard_path_crc32: int


@dataclass(frozen=True)
class ZXHInfoZipUnixV2(ZipExtraHeaderInterpretation):
    uid: Optional[PosixUID] = None
    gid: Optional[PosixGID] = None


@dataclass(frozen=True)
class ZXHInfoZipUnixV3(ZipExtraHeaderInterpretation):
    data: Optional['IZUnixV3Data']


@dataclass(frozen=True)
class IZUnixV3Data:
    pass


@dataclass(frozen=True)
class IZUnixV3DataUnsupported(IZUnixV3Data):
    format_version: int
    raw_data: bytes


@dataclass(frozen=True)
class IZUnixV3DataV1(IZUnixV3Data):
    uid: PosixUID
    gid: PosixGID


@dataclass(frozen=True)
class ZXHJARMarker(ZipExtraHeaderInterpretation):
    pass


class ZipExtraFieldsError(Exception):
    pass


class MalformedZipExtraDataError(ZipExtraFieldsError):
    pass
