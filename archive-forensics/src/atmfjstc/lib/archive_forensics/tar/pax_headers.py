from dataclasses import dataclass, field, replace
from typing import Dict, Optional, Tuple

from atmfjstc.lib.py_lang_utils.convert_struct import make_struct_converter
from atmfjstc.lib.iso_timestamp import iso_from_unix_time_string, ISOTimestamp
from atmfjstc.lib.os_forensics.posix import INodeNo, PosixDeviceIDKDevTFormat


@dataclass(frozen=True)
class TarArchivePaxHeaders:
    """
    Data structure for storing interpreted TAR PAX headers that add extra information about the archive itself as
    opposed to the entries.

    Note that there are no such headers yet defined in the official spec, but if any extra archive-level metadata is
    ever specified, it will likely use PAX headers for implementation.

    Also, "archive-level" and "global" are two different concepts, although archive-level headers will almost certainly
    have to be global headers.
    """
    unhandled_headers: Dict[str, str] = field(default_factory=dict)


def parse_tar_archive_pax_headers(raw_headers: Dict[str, str]) -> TarArchivePaxHeaders:
    return TarArchivePaxHeaders(
        # No per-archive headers defined yet
        unhandled_headers=raw_headers.copy(),  # Intentional copy
    )


@dataclass(frozen=True)
class TarArchiveEntryPaxHeaders:
    complete_path: Optional[str] = None
    mtime: Optional[ISOTimestamp] = None
    ctime: Optional[ISOTimestamp] = None
    atime: Optional[ISOTimestamp] = None
    inode: Optional[INodeNo] = None
    host_device_kdev: Optional[PosixDeviceIDKDevTFormat] = None
    n_links: Optional[int] = None
    creation_time: Optional[ISOTimestamp] = None

    unhandled_headers: Dict[str, str] = field(default_factory=dict)


def parse_tar_entry_pax_headers(raw_headers: Dict[str, str]) -> TarArchiveEntryPaxHeaders:
    result, unhandled = _convert_entry_headers(raw_headers)

    return TarArchiveEntryPaxHeaders(
        **result,
        unhandled_headers=unhandled,
    )


def parse_tar_archive_and_entry_pax_headers(
    raw_headers: Dict[str, str]
) -> Tuple[TarArchivePaxHeaders, TarArchiveEntryPaxHeaders]:
    """
    Convenience function for extracting both archive-level and entry-level headers, useful particularly for handling
    the global headers, which contain both (entry-level headers there apply to all files).
    """
    archive_headers = parse_tar_archive_pax_headers(raw_headers)
    entry_pax_headers = parse_tar_entry_pax_headers(archive_headers.unhandled_headers)

    archive_headers = replace(archive_headers, unhandled_headers=entry_pax_headers.unhandled_headers)

    return archive_headers, entry_pax_headers


_convert_entry_headers = make_struct_converter(
    source_type='dict',
    dest_type='dict',
    fields=dict(
        complete_path=dict(src='path'),
        mtime=dict(convert=lambda x: iso_from_unix_time_string(x)),
        ctime=dict(convert=lambda x: iso_from_unix_time_string(x)),
        atime=dict(convert=lambda x: iso_from_unix_time_string(x)),
        # SCHILY.* headers are added by the `star` program by Jörg Schilling
        inode=dict(src='SCHILY.ino', convert=INodeNo),
        host_device_kdev=dict(src='SCHILY.dev', convert=PosixDeviceIDKDevTFormat),
        n_links=dict(src='SCHILY.nlink', convert=int),
        # libarchive headers
        creation_time=dict(src='LIBARCHIVE.creationtime', convert=lambda x: iso_from_unix_time_string(x)),
    ),
    return_unparsed=True,
)
