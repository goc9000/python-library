"""
Utilities for handling ZIP "extra data" fields
"""

from typing import List, Dict, Callable

from atmfjstc.lib.binary_utils.BinaryReader import BinaryReader
from atmfjstc.lib.iso_timestamp import iso_from_unix_time

from . import ZipExtraHeader, ZipExtraHeaderInterpretation, MalformedZipExtraDataError, ZXHZip64, ZXHPkWareNTFS, \
    ZXHPkWareUnix, ZXHNTSecurityDescriptor, ZXHExtendedTimestamps, ZXHInfoZipUnixV1, ZXHInfoZipUnicodeComment, \
    ZXHInfoZipUnicodePath, ZXHInfoZipUnixV2, ZXHInfoZipUnixV3, ZXHJARMarker, NTFSInfoTag, NTFSInfoUnhandledTag, \
    NTSecurityDescriptorData, NTSecurityDescriptorDataDecompressed, NTSecurityDescriptorDataCompressed, \
    IZUnicodeCommentData, IZUnicodeCommentDataUnsupported, IZUnicodePathData, IZUnicodePathDataUnsupported, \
    IZUnixV3Data, IZUnixV3DataUnsupported


def parse_zip_extra_data(data: bytes, is_local: bool) -> List[ZipExtraHeader]:
    result = []

    reader = BinaryReader(data, big_endian=False)

    try:
        for header_id, value in reader.iter_tlv(type_bytes=2, length_bytes=2, meaning='ZIP extra headers'):
            result.append(_parse_header_from_tlv(header_id, value, is_local))
    except Exception as e:
        raise MalformedZipExtraDataError(
            f"Malformed binary data for ZIP {'local' if is_local else 'central'} extra field"
        ) from e

    return result


def _parse_header_from_tlv(header_id: int, data: bytes, is_local: bool) -> ZipExtraHeader:
    reader = BinaryReader(data, big_endian=False)

    parser = _PARSERS_BY_MAGIC.get(header_id)

    if parser is None:
        return ZipExtraHeader(
            magic=header_id,
            is_local=is_local,
            interpretation=None,
            warnings=(),
            unconsumed_data=reader.read_remainder()
        )

    warnings = []
    interpretation = parser(reader, is_local, warnings)

    unconsumed_data = None

    if not reader.eof():
        warnings.append("Header was not fully consumed")
        unconsumed_data = reader.read_remainder()

    return ZipExtraHeader(
        magic=header_id,
        is_local=is_local,
        interpretation=interpretation,
        warnings=tuple(warnings),
        unconsumed_data=unconsumed_data,
    )


def _parse_zip64(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHZip64:
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

    return ZXHZip64(sizes, disk_start_no)


def _parse_pkware_ntfs(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHPkWareNTFS:
    reserved = reader.read_uint32('reserved field')

    tags = tuple(NTFSInfoTag.parse(tag, value) for tag, value in reader.iter_tlv(type_bytes=2, length_bytes=2))

    unhandled = set(tag.tag for tag in tags if isinstance(tag, NTFSInfoUnhandledTag))

    if len(unhandled) > 0:
        mut_warnings.append(f"Unhandled tag(s) of type {', '.join(str(tag) for tag in unhandled)}")

    return ZXHPkWareNTFS(tags, reserved)


def _parse_pkware_unix(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHPkWareUnix:
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
        atime=iso_from_unix_time(raw_atime),
        mtime=iso_from_unix_time(raw_mtime),
        uid=uid, gid=gid, device=device, link_target=link_target
    )


def _parse_nt_security_descriptor(
    reader: BinaryReader, is_local: bool, mut_warnings: List[str]
) -> ZXHNTSecurityDescriptor:
    descriptor_size = reader.read_uint32('descriptor size')
    data = None

    if is_local:
        data = NTSecurityDescriptorData.parse(reader)

        if isinstance(data, NTSecurityDescriptorDataCompressed):
            mut_warnings.append("Failed to decompress descriptor")
        elif data.__class__ == NTSecurityDescriptorDataDecompressed:
            mut_warnings.append("Don't know how to decode this format version")

    return ZXHNTSecurityDescriptor(descriptor_size, data)


def _parse_extended_timestamps(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHExtendedTimestamps:
    flags = reader.read_uint8('flags')

    if flags > 7:
        mut_warnings.append("Flags are set beyond bits 0-2, don't know how to handle those")

    # The spec states that, for the central version of this header, only the mtime is included, with the flags
    # being an irrelevant copy of those from the local version. In practice, this rule seems to be disregarded,
    # with some programs (including zipinfo itself) treating the central header just like the local one. We try
    # to handle both situations here.

    n_fields = reader.bytes_remaining() >> 2

    if (not is_local) and (n_fields < 2):
        mtime = iso_from_unix_time(reader.read_uint32('mtime')) if (n_fields > 0) else None
        atime = None
        ctime = None
    else:
        mtime = iso_from_unix_time(reader.read_uint32('mtime')) if flags & (1 << 0) else None
        atime = iso_from_unix_time(reader.read_uint32('atime')) if flags & (1 << 1) else None

        # Despite the spec claiming this is the "creation time", in practice it seems to be the ctime with all the
        # ambiguity that implies
        ctime = iso_from_unix_time(reader.read_uint32('ctime')) if flags & (1 << 2) else None

    return ZXHExtendedTimestamps(mtime=mtime, atime=atime, ctime=ctime)


def _parse_infozip_unix_v1(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHInfoZipUnixV1:
    raw_atime, raw_mtime = reader.read_struct('II', 'timestamps')

    if not reader.eof():
        uid, gid = reader.read_struct('HH', 'UID/GID')
    else:
        uid = gid = None

    return ZXHInfoZipUnixV1(
        mtime=iso_from_unix_time(raw_mtime), atime=iso_from_unix_time(raw_atime), uid=uid, gid=gid,
    )


def _parse_infozip_unicode_comment(
    reader: BinaryReader, is_local: bool, mut_warnings: List[str]
) -> ZXHInfoZipUnicodeComment:
    data = IZUnicodeCommentData.parse(reader)

    if isinstance(data, IZUnicodeCommentDataUnsupported):
        mut_warnings.append(f"Don't know how to decode this format version")

    return ZXHInfoZipUnicodeComment(data)


def _parse_infozip_unicode_path(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHInfoZipUnicodePath:
    data = IZUnicodePathData.parse(reader)

    if isinstance(data, IZUnicodePathDataUnsupported):
        mut_warnings.append("Don't know how to decode this format version")

    return ZXHInfoZipUnicodePath(data)


def _parse_infozip_unix_v2(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHInfoZipUnixV2:
    if is_local:
        uid, gid = reader.read_struct('HH', 'UID/GID')
    else:
        uid = gid = None

    return ZXHInfoZipUnixV2(uid=uid, gid=gid)


def _parse_infozip_unix_v3(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHInfoZipUnixV3:
    data = IZUnixV3Data.parse(reader)

    if isinstance(data, IZUnixV3DataUnsupported):
        mut_warnings.append("Don't know how to decode this format version")

    return ZXHInfoZipUnixV3(data)


def _parse_jar_marker(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHJARMarker:
    return ZXHJARMarker()


_PARSERS_BY_MAGIC : Dict[int, Callable[[BinaryReader, bool, List[str]], ZipExtraHeaderInterpretation]] = {
    0x0001: _parse_zip64,
    0x000a: _parse_pkware_ntfs,
    0x000d: _parse_pkware_unix,
    0x4453: _parse_nt_security_descriptor,
    0x5455: _parse_extended_timestamps,
    0x5855: _parse_infozip_unix_v1,
    0x6375: _parse_infozip_unicode_comment,
    0x7075: _parse_infozip_unicode_path,
    0x7855: _parse_infozip_unix_v2,
    0x7875: _parse_infozip_unix_v3,
    0xcafe: _parse_jar_marker,
}
