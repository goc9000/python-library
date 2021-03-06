"""
Utilities for handling ZIP "extra data" fields
"""

from dataclasses import dataclass, replace, field
from typing import List, Optional, Dict, Tuple, Type, TypeVar, ClassVar

from atmfjstc.lib.binary_utils.BinaryReader import BinaryReader
from atmfjstc.lib.iso_timestamp import ISOTimestamp, iso_from_unix_time
from atmfjstc.lib.os_forensics.windows import iso_from_ntfs_time
from atmfjstc.lib.os_forensics.windows.security import NTSecurityDescriptor
from atmfjstc.lib.os_forensics.windows.security.parse import decode_nt_security_descriptor
from atmfjstc.lib.os_forensics.posix import PosixUID, PosixGID, PosixDeviceID

from atmfjstc.lib.archive_forensics.zip import decompress_now


def parse_zip_central_extra_data(field_bytes: bytes) -> List['ZipExtraHeader']:
    return _parse_zip_extra_data(field_bytes, is_local=False)


def parse_zip_local_extra_data(field_bytes: bytes) -> List['ZipExtraHeader']:
    return _parse_zip_extra_data(field_bytes, is_local=True)


def _parse_zip_extra_data(data: bytes, is_local: bool) -> List['ZipExtraHeader']:
    result = []

    reader = BinaryReader(data, big_endian=False)

    try:
        for header_id, value in reader.iter_tlv(type_bytes=2, length_bytes=2, meaning='ZIP extra headers'):
            result.append(ZipExtraHeader.parse_from_tlv(header_id, value, is_local))
    except Exception as e:
        raise MalformedZipExtraDataError(
            f"Malformed binary data for ZIP {'local' if is_local else 'central'} extra field"
        ) from e

    return result


@dataclass(frozen=True)
class ZipExtraHeader:
    magic: int
    is_local: bool
    warnings: Tuple[str, ...]
    unconsumed_data: Optional[bytes]

    def description(self) -> str:
        return f"ZIP {'local' if self.is_local else 'central'} extra header of type " + \
               (self.__class__.__name__ if not isinstance(self, ZXHUnrecognized) else f"0x{self.magic:04x}")

    @staticmethod
    def parse_from_tlv(header_id: int, data: bytes, is_local: bool) -> 'ZipExtraHeader':
        reader = BinaryReader(data, big_endian=False)

        header_class = ZipExtraHeader.get_header_class_for_magic(header_id)
        if header_class is None:
            return ZXHUnrecognized(header_id, is_local, (), None, reader.read_remainder())

        result = header_class.parse(reader, is_local)

        if not reader.eof():
            result = replace(
                result,
                warnings=(*result.warnings, "Header was not fully consumed"),
                unconsumed_data=reader.read_remainder()
            )

        return result

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZipExtraHeader':
        raise NotImplementedError("Must override this in concrete header classes")

    _cached_header_index: ClassVar[Optional[Dict[int, Type['ZipExtraHeader']]]] = None

    @classmethod
    def get_header_class_for_magic(cls, magic: int) -> Optional[Type['ZipExtraHeader']]:
        if cls._cached_header_index is None:
            cls._cached_header_index = { header_class.magic: header_class for header_class in _ALL_HEADER_CLASSES }

        return cls._cached_header_index.get(magic)


@dataclass(frozen=True)
class ZXHUnrecognized(ZipExtraHeader):
    raw_data: bytes


@dataclass(frozen=True)
class ZXHZip64(ZipExtraHeader):
    magic: int = field(default=0x0001, init=False)
    sizes: Tuple[int, ...]
    disk_start_no: Optional[int]

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHZip64':
        # Due to the way this header works (subfields may be included or omitted depending on other fields in the
        # local/central directory record), we can't decode it here completely as we need a lot more context. So we just
        # return a list of unmarked 64-bit sizes, and the 32-bit disk start number.

        total_bytes = reader.bytes_remaining()

        if (total_bytes > 28) or (total_bytes % 4 != 0):
            raise MalformedZipExtraDataError(
                f"ZIP64 extra header size should be a multiple of 4 between 0 and 28, but it is {total_bytes}"
            )

        n_64bit_values = total_bytes >> 3
        sizes = reader.read_struct(f'{n_64bit_values}Q', '64-bit sizes') if n_64bit_values > 0 else ()
        disk_start_no = reader.read_uint32('disk start no.') if (total_bytes % 8 != 0) else None

        return ZXHZip64(is_local, (), None, sizes, disk_start_no)


TagT = TypeVar('TagT', bound='NTFSInfoTag')


@dataclass(frozen=True)
class ZXHPkWareNTFS(ZipExtraHeader):
    magic: int = field(default=0x000a, init=False)
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

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHPkWareNTFS':
        reserved = reader.read_uint32('reserved field')

        tags = tuple(NTFSInfoTag.parse(tag, value) for tag, value in reader.iter_tlv(type_bytes=2, length_bytes=2))

        unhandled = set(tag.tag for tag in tags if isinstance(tag, NTFSInfoUnhandledTag))
        warnings = (f"Unhandled tag(s) of type {', '.join(str(tag) for tag in unhandled)}",) if len(
            unhandled) > 0 else ()

        return ZXHPkWareNTFS(is_local, warnings, None, tags, reserved)


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
class ZXHPkWareUnix(ZipExtraHeader):
    magic: int = field(default=0x000d, init=False)
    atime: ISOTimestamp
    mtime: ISOTimestamp
    uid: PosixUID
    gid: PosixGID
    device: Optional[PosixDeviceID] = None
    link_target: Optional[bytes] = None

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHPkWareUnix':
        raw_atime, raw_mtime, uid, gid = reader.read_struct('IIHH')
        device = link_target = None

        special_data = reader.read_remainder()

        # KLUDGE: normally we'd need to know the type of the file to know whether special_data represents the link
        # target (for sym/hardlinks) or the major/minor device numbers (for char/block devices). We use a trick instead.
        # Given that the major number is almost certainly 16 bits at best, there will almost definitely be a \x00 byte
        # in the special data, whereas for a link this will definitely not be the case.

        if (len(special_data) == 8) and (b'\x00' in special_data):
            device = BinaryReader(special_data, big_endian=False).read_struct('II')
        else:
            link_target = special_data

        return ZXHPkWareUnix(
            is_local, (), None,
            atime=iso_from_unix_time(raw_atime),
            mtime=iso_from_unix_time(raw_mtime),
            uid=uid, gid=gid, device=device, link_target=link_target
        )


@dataclass(frozen=True)
class ZXHNTSecurityDescriptor(ZipExtraHeader):
    magic: int = field(default=0x4453, init=False)
    uncompressed_data_size: int
    data: Optional['NTSecurityDescriptorData']

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHNTSecurityDescriptor':
        descriptor_size = reader.read_uint32('descriptor size')
        data = None
        warnings = ()

        if is_local:
            data = NTSecurityDescriptorData.parse(reader)

            if isinstance(data, NTSecurityDescriptorDataCompressed):
                warnings = (f"Failed to decompress descriptor",)
            elif data.__class__ == NTSecurityDescriptorDataDecompressed:
                warnings = (f"Don't know how to decode this format version",)

        return ZXHNTSecurityDescriptor(is_local, warnings, None, descriptor_size, data)


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
class ZXHExtendedTimestamps(ZipExtraHeader):
    magic: int = field(default=0x5455, init=False)
    mtime: Optional[ISOTimestamp] = None
    atime: Optional[ISOTimestamp] = None
    ctime: Optional[ISOTimestamp] = None

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHExtendedTimestamps':
        flags = reader.read_uint8('flags')

        mtime = iso_from_unix_time(reader.read_uint32('mtime')) if flags & (1 << 0) else None
        atime = iso_from_unix_time(reader.read_uint32('atime')) if is_local and (flags & (1 << 1)) else None
        ctime = iso_from_unix_time(reader.read_uint32('ctime')) if is_local and (flags & (1 << 2)) else None

        return ZXHExtendedTimestamps(is_local, (), None, mtime=mtime, atime=atime, ctime=ctime)


@dataclass(frozen=True)
class ZXHInfoZipUnixV1(ZipExtraHeader):
    magic: int = field(default=0x5855, init=False)
    mtime: ISOTimestamp
    atime: ISOTimestamp
    uid: Optional[PosixUID] = None
    gid: Optional[PosixGID] = None

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHInfoZipUnixV1':
        raw_atime, raw_mtime = reader.read_struct('II', 'timestamps')

        if not reader.eof():
            uid, gid = reader.read_struct('HH', 'UID/GID')
        else:
            uid = gid = None

        return ZXHInfoZipUnixV1(
            is_local, (), None,
            mtime=iso_from_unix_time(raw_mtime), atime=iso_from_unix_time(raw_atime), uid=uid, gid=gid,
        )


@dataclass(frozen=True)
class ZXHInfoZipUnicodeComment(ZipExtraHeader):
    magic: int = field(default=0x6375, init=False)
    data: Optional['IZUnicodeCommentData']

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHInfoZipUnicodeComment':
        data = IZUnicodeCommentData.parse(reader)

        warnings = ()
        if isinstance(data, IZUnicodeCommentDataUnsupported):
            warnings = (f"Don't know how to decode this format version",)

        return ZXHInfoZipUnicodeComment(is_local, warnings, None, data)


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
class ZXHInfoZipUnicodePath(ZipExtraHeader):
    magic: int = field(default=0x7075, init=False)
    data: Optional['IZUnicodePathData']

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHInfoZipUnicodePath':
        data = IZUnicodePathData.parse(reader)

        warnings = ()
        if isinstance(data, IZUnicodePathDataUnsupported):
            warnings = (f"Don't know how to decode this format version",)

        return ZXHInfoZipUnicodePath(is_local, warnings, None, data)


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
class ZXHInfoZipUnixV2(ZipExtraHeader):
    magic: int = field(default=0x7855, init=False)
    uid: Optional[PosixUID] = None
    gid: Optional[PosixGID] = None

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHInfoZipUnixV2':
        if is_local:
            uid, gid = reader.read_struct('HH', 'UID/GID')
        else:
            uid = gid = None

        return ZXHInfoZipUnixV2(is_local, (), None, uid=uid, gid=gid)


@dataclass(frozen=True)
class ZXHInfoZipUnixV3(ZipExtraHeader):
    magic: int = field(default=0x7875, init=False)
    data: Optional['IZUnixV3Data']

    @staticmethod
    def parse(reader: BinaryReader, is_local: bool) -> 'ZXHInfoZipUnixV3':
        data = IZUnixV3Data.parse(reader)

        warnings = ()
        if isinstance(data, IZUnixV3DataUnsupported):
            warnings = (f"Don't know how to decode this format version",)

        return ZXHInfoZipUnixV3(is_local, warnings, None, data)


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


_ALL_HEADER_CLASSES : List[Type[ZipExtraHeader]] = [
    ZXHZip64, ZXHPkWareNTFS, ZXHPkWareUnix, ZXHNTSecurityDescriptor, ZXHExtendedTimestamps, ZXHInfoZipUnixV1,
    ZXHInfoZipUnicodeComment, ZXHInfoZipUnicodePath, ZXHInfoZipUnixV2, ZXHInfoZipUnixV3,
]


class ZipExtraFieldsError(Exception):
    pass


class MalformedZipExtraDataError(ZipExtraFieldsError):
    pass
