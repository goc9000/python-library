from dataclasses import dataclass, field
from typing import Dict, Optional

from atmfjstc.lib.py_lang_utils.convert_struct import make_struct_converter
from atmfjstc.lib.iso_timestamp import iso_from_unix_time_string, ISOTimestamp
from atmfjstc.lib.os_forensics.posix import INodeNo, PosixDeviceIDKDevTFormat


@dataclass(frozen=True)
class TarArchivePaxHeaders:
    unhandled_headers: Dict[str, str] = field(default_factory=dict)


def parse_tar_archive_pax_headers(raw_headers: Dict[str, str]) -> TarArchivePaxHeaders:
    return TarArchivePaxHeaders(
        # No per-archive headers supported yet
        unhandled_headers=raw_headers,
    )


@dataclass(frozen=True)
class TarArchiveEntryPaxHeaders:
    complete_path: Optional[str] = None
    ctime: Optional[ISOTimestamp] = None
    atime: Optional[ISOTimestamp] = None
    inode: Optional[INodeNo] = None
    host_device_kdev: Optional[PosixDeviceIDKDevTFormat] = None
    n_links: Optional[int] = None
    creation_time: Optional[ISOTimestamp] = None

    unhandled_headers: Dict[str, str] = field(default_factory=dict)


def parse_tar_entry_pax_headers(raw_headers: Dict[str, str]) -> TarArchiveEntryPaxHeaders:
    result, unhandled = _convert_tar_entry(raw_headers)

    return TarArchiveEntryPaxHeaders(
        **result,
        unhandled_headers=unhandled,
    )


_convert_tar_entry = make_struct_converter(
    source_type='dict',
    dest_type='dict',
    fields=dict(
        complete_path=dict(src='path'),
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
