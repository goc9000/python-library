from typing import Union

from atmfjstc.lib.binary_utils.BinaryReader import BinaryReader

from atmfjstc.lib.os_forensics.windows.security import NTSecurityID, NTGuid


def decode_nt_security_id(raw_data: Union[bytes, BinaryReader]) -> NTSecurityID:
    reader = _init_reader(raw_data)

    revision, n_sub_auth = reader.read_struct('BB', "NT SID header")

    # The authority is a big-endian int, unlike all the others
    authority = reader.read_fixed_size_int(6, "authority", big_endian=True, signed=False)
    subauthorities = reader.read_struct(f'{n_sub_auth}I', "subauthorities")

    return NTSecurityID(revision, authority, subauthorities)


def decode_nt_guid(raw_data: Union[bytes, BinaryReader]) -> NTGuid:
    reader = _init_reader(raw_data)

    group1, group2, group3 = reader.read_struct('IHH', "NT GUID, groups 1-3")

    # The last 2 parts are big-endian, unlike the previous three. Windows is weird like that.
    group4 = reader.read_uint16("NT GUID group 4", big_endian=True)
    group5 = reader.read_fixed_size_int(6, "NT GUID group 5", big_endian=True, signed=False)

    return NTGuid(group1, group2, group3, group4, group5)


def _init_reader(raw_data: Union[bytes, BinaryReader]) -> BinaryReader:
    if isinstance(raw_data, BinaryReader):
        return raw_data
    else:
        return BinaryReader(raw_data, big_endian=False)
