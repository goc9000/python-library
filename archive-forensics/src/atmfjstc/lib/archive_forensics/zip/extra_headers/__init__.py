"""
Utilities for handling ZIP "extra data" fields
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Type, TypeVar

from atmfjstc.lib.binary_utils.BinaryReader import BinaryReader
from atmfjstc.lib.iso_timestamp import ISOTimestamp
from atmfjstc.lib.os_forensics.windows import iso_from_ntfs_time
from atmfjstc.lib.os_forensics.windows.security import NTSecurityDescriptor
from atmfjstc.lib.os_forensics.windows.security.parse import decode_nt_security_descriptor
from atmfjstc.lib.os_forensics.posix import PosixUID, PosixGID, PosixDeviceID

from .. import decompress_now


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
    interpretation: Optional['ZipExtraHeaderInterpretation']
    warnings: Tuple[str, ...]
    unconsumed_data: Optional[bytes]

    @property
    def is_unrecognized(self) -> bool:
        return self.interpretation is None

    def description(self) -> str:
        return f"ZIP {'local' if self.is_local else 'central'} extra header of type " + \
               (f"0x{self.magic:04x}" if self.is_unrecognized else self.interpretation.__class__.__name__)


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
    tag: int

    @staticmethod
    def parse(tag: int, value: bytes) -> 'NTFSInfoTag':
        reader = BinaryReader(value, big_endian=False)

        if tag == 1:
            return NTFSInfoTimestampsTag(*(
                iso_from_ntfs_time(raw_time) for raw_time in reader.read_struct('QQQ', 'timestamps')
            ))

        return NTFSInfoUnhandledTag(tag, value)


@dataclass(frozen=True)
class NTFSInfoTimestampsTag(NTFSInfoTag):
    tag: int = field(default=1, init=False)
    mtime: ISOTimestamp
    atime: ISOTimestamp
    ctime: ISOTimestamp


@dataclass(frozen=True)
class NTFSInfoUnhandledTag(NTFSInfoTag):
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

    @staticmethod
    def parse(reader: BinaryReader) -> 'NTSecurityDescriptorData':
        version, compress_type, crc = reader.read_struct('BHI')
        compressed_data = reader.read_remainder()

        try:
            raw_data = decompress_now(compressed_data, compress_type)
        except Exception:
            return NTSecurityDescriptorDataCompressed(version, compress_type, compressed_data)

        if version == 0:
            return NTSecurityDescriptorDataV0(compress_type, raw_data, decode_nt_security_descriptor(raw_data))

        return NTSecurityDescriptorDataDecompressed(version, compress_type, raw_data)


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
    format_version: int

    @staticmethod
    def parse(reader: BinaryReader) -> 'IZUnicodeCommentData':
        version = reader.read_uint8('version')

        if version == 1:
            standard_comment_crc32 = reader.read_uint32('CRC32')
            comment = reader.read_remainder().decode('utf-8')
            return IZUnicodeCommentDataV1(comment, standard_comment_crc32)
        else:
            return IZUnicodeCommentDataUnsupported(version, reader.read_remainder())


@dataclass(frozen=True)
class IZUnicodeCommentDataUnsupported(IZUnicodeCommentData):
    raw_data: bytes


@dataclass(frozen=True)
class IZUnicodeCommentDataV1(IZUnicodeCommentData):
    format_version: int = field(default=1, init=False)
    comment: str
    standard_comment_crc32: int


@dataclass(frozen=True)
class ZXHInfoZipUnicodePath(ZipExtraHeaderInterpretation):
    data: Optional['IZUnicodePathData']


@dataclass(frozen=True)
class IZUnicodePathData:
    format_version: int

    @staticmethod
    def parse(reader: BinaryReader) -> 'IZUnicodePathData':
        version = reader.read_uint8('version')

        if version == 1:
            standard_path_crc32 = reader.read_uint32('CRC32')
            path = reader.read_remainder().decode('utf-8')
            return IZUnicodePathDataV1(path, standard_path_crc32)
        else:
            return IZUnicodePathDataUnsupported(version, reader.read_remainder())


@dataclass(frozen=True)
class IZUnicodePathDataUnsupported(IZUnicodePathData):
    raw_data: bytes


@dataclass(frozen=True)
class IZUnicodePathDataV1(IZUnicodePathData):
    format_version: int = field(default=1, init=False)
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
    format_version: int

    @staticmethod
    def parse(reader: BinaryReader) -> 'IZUnixV3Data':
        version = reader.read_uint8('version')

        if version == 1:
            uid_size = reader.read_uint8('UID size')
            uid = PosixUID(reader.read_fixed_size_int(uid_size, signed=False, meaning='UID'))
            gid_size = reader.read_uint8('GID size')
            gid = PosixGID(reader.read_fixed_size_int(gid_size, signed=False, meaning='GID'))

            return IZUnixV3DataV1(uid, gid)
        else:
            return IZUnixV3DataUnsupported(version, reader.read_remainder())


@dataclass(frozen=True)
class IZUnixV3DataUnsupported(IZUnixV3Data):
    raw_data: bytes


@dataclass(frozen=True)
class IZUnixV3DataV1(IZUnixV3Data):
    format_version: int = field(default=1, init=False)
    uid: PosixUID
    gid: PosixGID


@dataclass(frozen=True)
class ZXHJARMarker(ZipExtraHeaderInterpretation):
    pass


class ZipExtraFieldsError(Exception):
    pass


class MalformedZipExtraDataError(ZipExtraFieldsError):
    pass
