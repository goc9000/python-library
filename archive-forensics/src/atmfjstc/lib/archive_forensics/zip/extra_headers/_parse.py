"""
Utilities for handling ZIP "extra data" fields
"""

from typing import List, Dict, Callable, Tuple, Type

from atmfjstc.lib.binary_utils.BinaryReader import BinaryReader
from atmfjstc.lib.iso_timestamp import iso_from_unix_time

from atmfjstc.lib.os_forensics.windows import iso_from_ntfs_time
from atmfjstc.lib.os_forensics.windows.security.parse import decode_nt_security_descriptor
from atmfjstc.lib.os_forensics.posix import PosixUID, PosixGID

from .. import decompress_now

from . import ZipExtraHeader, ZipExtraHeaderInterpretation, ZXHZip64, ZXHPkWareNTFS, ZXHPkWareUnix, \
    ZXHNTSecurityDescriptor, ZXHExtendedTimestamps, ZXHInfoZipUnixV1, ZXHInfoZipUnicodeComment, \
    ZXHInfoZipUnicodePath, ZXHInfoZipUnixV2, ZXHInfoZipUnixV3, ZXHJARMarker, NTFSInfoTag, NTFSInfoUnhandledTag, \
    NTSecurityDescriptorData, NTSecurityDescriptorDataDecompressed, NTSecurityDescriptorDataCompressed, \
    IZUnicodeCommentData, IZUnicodeCommentDataUnsupported, IZUnicodePathData, IZUnicodePathDataUnsupported, \
    IZUnixV3Data, IZUnixV3DataUnsupported, NTFSInfoTimestampsTag, NTSecurityDescriptorDataV0, IZUnicodeCommentDataV1, \
    IZUnicodePathDataV1, IZUnixV3DataV1, ZXHXceedUnicodeData


def parse_zip_extra_data(data: bytes, is_local: bool) -> List[ZipExtraHeader]:
    result = []

    reader = BinaryReader(data, big_endian=False)
    last_ok_position = 0

    try:
        for header_id, value in reader.iter_tlv(type_bytes=2, length_bytes=2, meaning='ZIP extra headers'):
            result.append(_parse_header_from_tlv(header_id, value, is_local))
            last_ok_position = reader.tell()
    except Exception as e:
        result.append(ZipExtraHeader(
            magic=0,
            is_local=is_local,
            parse_error=e,
            unconsumed_data=data[last_ok_position:],
        ))

    return result


def _parse_header_from_tlv(header_id: int, data: bytes, is_local: bool) -> ZipExtraHeader:
    interpretation_type, parser = _INTERPRETATIONS_BY_MAGIC.get(header_id, (None, None))

    if parser is None:
        return ZipExtraHeader(
            magic=header_id,
            is_local=is_local,
            unconsumed_data=data
        )

    reader = BinaryReader(data, big_endian=False)

    interpretation = None
    warnings = []
    parse_error = None
    unconsumed_data = b''

    try:
        interpretation = parser(reader, is_local, warnings)
    except Exception as e:
        parse_error = e

    if not reader.eof():
        warnings.append("Header was not fully consumed")
        unconsumed_data = reader.read_remainder()

    return ZipExtraHeader(
        magic=header_id,
        is_local=is_local,
        interpretation_type=interpretation_type,
        interpretation=interpretation,
        parse_error=parse_error,
        warnings=tuple(warnings),
        unconsumed_data=unconsumed_data,
    )


def _parse_zip64(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHZip64:
    # Due to the way this header works (subfields may be included or omitted depending on other fields in the
    # local/central directory record), we can't decode it here completely as we need a lot more context. So we just
    # return a list of unmarked 64-bit sizes, and the 32-bit disk start number.

    total_bytes = reader.bytes_remaining()

    if (total_bytes > 28) or (total_bytes % 4 != 0):
        raise AssertionError(
            f"ZIP64 extra header size should be a multiple of 4 between 0 and 28, but it is {total_bytes}"
        )

    n_64bit_values = total_bytes >> 3
    sizes = reader.read_struct(f'{n_64bit_values}Q', '64-bit sizes') if n_64bit_values > 0 else ()
    disk_start_no = reader.read_uint32('disk start no.') if (total_bytes % 8 != 0) else None

    return ZXHZip64(sizes, disk_start_no)


def _parse_pkware_ntfs(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHPkWareNTFS:
    reserved = reader.read_uint32('reserved field')

    tags = tuple(_parse_ntfs_info_tag(tag, value) for tag, value in reader.iter_tlv(type_bytes=2, length_bytes=2))

    unhandled = set(tag.tag for tag in tags if isinstance(tag, NTFSInfoUnhandledTag))

    if len(unhandled) > 0:
        mut_warnings.append(f"Unhandled tag(s) of type {', '.join(str(tag) for tag in unhandled)}")

    return ZXHPkWareNTFS(tags, reserved)


def _parse_ntfs_info_tag(tag: int, value: bytes) -> NTFSInfoTag:
    reader = BinaryReader(value, big_endian=False)

    if tag == 1:
        return NTFSInfoTimestampsTag(*(
            iso_from_ntfs_time(raw_time) for raw_time in reader.read_struct('QQQ', 'timestamps')
        ))

    return NTFSInfoUnhandledTag(tag, value)


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
        data = _parse_nt_security_descriptor_data(reader)

        if isinstance(data, NTSecurityDescriptorDataCompressed):
            mut_warnings.append("Failed to decompress descriptor")
        elif data.__class__ == NTSecurityDescriptorDataDecompressed:
            mut_warnings.append("Don't know how to decode this format version")

    return ZXHNTSecurityDescriptor(descriptor_size, data)


def _parse_nt_security_descriptor_data(reader: BinaryReader) -> NTSecurityDescriptorData:
    version, compress_type, crc = reader.read_struct('BHI')
    compressed_data = reader.read_remainder()

    try:
        raw_data = decompress_now(compressed_data, compress_type)
    except Exception:
        return NTSecurityDescriptorDataCompressed(version, compress_type, compressed_data)

    if version == 0:
        return NTSecurityDescriptorDataV0(compress_type, raw_data, decode_nt_security_descriptor(raw_data))

    return NTSecurityDescriptorDataDecompressed(version, compress_type, raw_data)


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


def _parse_xceed_unicode_data(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHXceedUnicodeData:
    # As per https://github.com/pmqs/zipdetails/issues/13

    reader.expect_magic(b'NUCX', "Xceed unicode header signatura ('NUCX')")

    unicode_path_len = reader.read_uint16('unicode path length')
    unicode_comment_len = reader.read_uint16('unicode comment length') if (not is_local) else 0

    raw_unicode_path = reader.read_amount(unicode_path_len * 2, 'UCS-16 path characters')
    raw_unicode_comment = reader.read_amount(unicode_comment_len * 2, 'UCS-16 comment characters')

    return ZXHXceedUnicodeData(
        unicode_path=raw_unicode_path.decode('utf-16') if raw_unicode_path != b'' else None,
        unicode_comment=raw_unicode_comment.decode('utf-16') if raw_unicode_comment != b'' else None,
    )


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
    data = _parse_infozip_unicode_comment_data(reader)

    if isinstance(data, IZUnicodeCommentDataUnsupported):
        mut_warnings.append(f"Don't know how to decode this format version")

    return ZXHInfoZipUnicodeComment(data)


def _parse_infozip_unicode_comment_data(reader: BinaryReader) -> IZUnicodeCommentData:
    version = reader.read_uint8('version')

    if version == 1:
        standard_comment_crc32 = reader.read_uint32('CRC32')
        comment = reader.read_remainder().decode('utf-8')
        return IZUnicodeCommentDataV1(comment, standard_comment_crc32)
    else:
        return IZUnicodeCommentDataUnsupported(version, reader.read_remainder())


def _parse_infozip_unicode_path(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHInfoZipUnicodePath:
    data = _parse_infozip_unicode_path_data(reader)

    if isinstance(data, IZUnicodePathDataUnsupported):
        mut_warnings.append("Don't know how to decode this format version")

    return ZXHInfoZipUnicodePath(data)


def _parse_infozip_unicode_path_data(reader: BinaryReader) -> IZUnicodePathData:
    version = reader.read_uint8('version')

    if version == 1:
        standard_path_crc32 = reader.read_uint32('CRC32')
        path = reader.read_remainder().decode('utf-8')
        return IZUnicodePathDataV1(path, standard_path_crc32)
    else:
        return IZUnicodePathDataUnsupported(version, reader.read_remainder())


def _parse_infozip_unix_v2(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHInfoZipUnixV2:
    if is_local:
        uid, gid = reader.read_struct('HH', 'UID/GID')
    else:
        uid = gid = None

    return ZXHInfoZipUnixV2(uid=uid, gid=gid)


def _parse_infozip_unix_v3(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHInfoZipUnixV3:
    data = _parse_infozip_unix_v3_data(reader)

    if isinstance(data, IZUnixV3DataUnsupported):
        mut_warnings.append("Don't know how to decode this format version")

    return ZXHInfoZipUnixV3(data)


def _parse_infozip_unix_v3_data(reader: BinaryReader) -> IZUnixV3Data:
    version = reader.read_uint8('version')

    if version == 1:
        uid_size = reader.read_uint8('UID size')
        uid = PosixUID(reader.read_fixed_size_int(uid_size, signed=False, meaning='UID'))
        gid_size = reader.read_uint8('GID size')
        gid = PosixGID(reader.read_fixed_size_int(gid_size, signed=False, meaning='GID'))

        return IZUnixV3DataV1(uid, gid)
    else:
        return IZUnixV3DataUnsupported(version, reader.read_remainder())


def _parse_jar_marker(reader: BinaryReader, is_local: bool, mut_warnings: List[str]) -> ZXHJARMarker:
    return ZXHJARMarker()


_INTERPRETATIONS_BY_MAGIC : Dict[
    int,
    Tuple[
        Type[ZipExtraHeaderInterpretation],
        Callable[[BinaryReader, bool, List[str]], ZipExtraHeaderInterpretation]
    ]
] = {
    0x0001: (ZXHZip64, _parse_zip64),
    0x000a: (ZXHPkWareNTFS, _parse_pkware_ntfs),
    0x000d: (ZXHPkWareUnix, _parse_pkware_unix),
    0x4453: (ZXHNTSecurityDescriptor, _parse_nt_security_descriptor),
    0x5455: (ZXHExtendedTimestamps, _parse_extended_timestamps),
    0x554e: (ZXHXceedUnicodeData, _parse_xceed_unicode_data),
    0x5855: (ZXHInfoZipUnixV1, _parse_infozip_unix_v1),
    0x6375: (ZXHInfoZipUnicodeComment, _parse_infozip_unicode_comment),
    0x7075: (ZXHInfoZipUnicodePath, _parse_infozip_unicode_path),
    0x7855: (ZXHInfoZipUnixV2, _parse_infozip_unix_v2),
    0x7875: (ZXHInfoZipUnixV3, _parse_infozip_unix_v3),
    0xcafe: (ZXHJARMarker, _parse_jar_marker),
}
