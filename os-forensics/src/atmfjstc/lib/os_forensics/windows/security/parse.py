from typing import Union, List

from atmfjstc.lib.binary_utils.BinaryReader import BinaryReader

from atmfjstc.lib.os_forensics.windows.security import NTSecurityID, NTGuid, NTSecurityDescriptor, NTSdTrusteeInfo, \
    NTSdACLInfo, NTAclEntry, NTAclEntryInheritFlags, NTStandardRights, NTSpecificRights, NTAllowAccessACLEntry, \
    NTDenyAccessACLEntry, NTSystemAuditACLEntry, NTSystemAlarmACLEntry, NTMandatoryLabelACLEntry
from atmfjstc.lib.os_forensics.windows.security.low_level import NTSdControlFlags, NTAclEntryType, NTAclEntryFlags, \
    NTStoredAccessMask, NTObjectSpecificACLFlags, NTMandatoryAccessPolicy


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


def decode_nt_security_descriptor(raw_data: Union[bytes, BinaryReader]) -> NTSecurityDescriptor:
    reader = _init_reader(raw_data)
    base_pos = reader.tell()

    reader = BinaryReader(raw_data, big_endian=False)

    revision = reader.read_uint8("NT Security Descriptor revision")

    if revision != 1:
        raise NotImplementedError(
            "NT Security Descriptor has revision {revision}, can only parse revision 1"
        )

    _pad_byte, ctrl_flags, owner_ptr, group_ptr, sacl_ptr, dacl_ptr = \
        reader.read_struct('BHIIII', 'NT Security Descriptor header')

    ctrl_flags = NTSdControlFlags(ctrl_flags)

    if NTSdControlFlags.SELF_RELATIVE not in ctrl_flags:
        raise ValueError("Can only parse self-relative NT Security Descriptors!")

    def _parse_trustee_info(offset: int, default_flag: NTSdControlFlags) -> NTSdTrusteeInfo:
        sid = None
        if offset != 0:
            reader.seek(base_pos + offset)
            sid = decode_nt_security_id(reader)

        return NTSdTrusteeInfo(
            sid=sid,
            defaulted=(default_flag in ctrl_flags),
        )

    def _parse_acl_info(offset: int, is_dacl: bool) -> NTSdACLInfo:
        is_present = (NTSdControlFlags.DACL_PRESENT if is_dacl else NTSdControlFlags.SACL_PRESENT) in ctrl_flags

        defaulted_flag = NTSdControlFlags.DACL_DEFAULTED if is_dacl else NTSdControlFlags.SACL_DEFAULTED
        auto_inh_flag = NTSdControlFlags.DACL_AUTO_INHERITED if is_dacl else NTSdControlFlags.SACL_AUTO_INHERITED
        auto_inh_req_flag = \
            NTSdControlFlags.DACL_AUTO_INHERIT_REQ if is_dacl else NTSdControlFlags.SACL_AUTO_INHERIT_REQ
        protected_flag = NTSdControlFlags.DACL_PROTECTED if is_dacl else NTSdControlFlags.SACL_PROTECTED

        entries = ()
        if offset != 0:
            reader.seek(base_pos + offset)
            entries = tuple(decode_nt_acl(reader))

        return NTSdACLInfo(
            present=is_present,
            null=is_present and (offset == 0),
            entries=entries,
            defaulted=is_present and (defaulted_flag in ctrl_flags),
            auto_inherited=auto_inh_flag in ctrl_flags,
            auto_inherit_req=auto_inh_req_flag in ctrl_flags,
            protected=protected_flag in ctrl_flags,
        )

    return NTSecurityDescriptor(
        owner=_parse_trustee_info(owner_ptr, NTSdControlFlags.OWNER_DEFAULTED),
        group=_parse_trustee_info(group_ptr, NTSdControlFlags.GROUP_DEFAULTED),

        dacl=_parse_acl_info(dacl_ptr, True),
        sacl=_parse_acl_info(sacl_ptr, False),

        rm_control_valid=(NTSdControlFlags.RM_CONTROL_VALID in ctrl_flags),
    )


def decode_nt_acl(raw_data: Union[bytes, BinaryReader]) -> List[NTAclEntry]:
    reader = _init_reader(raw_data)

    _revision, _pad1, _size, n_entries, _pad2 = reader.read_struct('BBHHH', "ACL header")

    def _parse_acl_entry():
        type, flags, size = reader.read_struct('BBH', "ACL entry header")
        ace_data = reader.read_amount(size - 4, "ACL entry data")

        return _decode_acl_entry(type, flags, ace_data)

    return [_parse_acl_entry() for _ in range(n_entries)]


def decode_nt_ace_inherit_flags(flags: NTAclEntryFlags) -> NTAclEntryInheritFlags:
    return NTAclEntryInheritFlags(
        objects=NTAclEntryFlags.OBJECT_INHERIT in flags,
        containers=NTAclEntryFlags.CONTAINER_INHERIT in flags,
        no_propagate=NTAclEntryFlags.NO_PROPAGATE_INHERIT in flags,
        inherit_only=NTAclEntryFlags.INHERIT_ONLY in flags,
        inherited=NTAclEntryFlags.INHERITED in flags,
    )


def decode_nt_standard_rights(access_mask: NTStoredAccessMask) -> NTStandardRights:
    return NTStandardRights(
        delete=NTStoredAccessMask.DELETE in access_mask,
        read_control=NTStoredAccessMask.READ_CONTROL in access_mask,
        write_dacl=NTStoredAccessMask.WRITE_DACL in access_mask,
        write_owner=NTStoredAccessMask.WRITE_OWNER in access_mask,
        synchronize=NTStoredAccessMask.SYNCHRONIZE in access_mask,
    )


def decode_nt_specific_rights(access_mask: NTStoredAccessMask) -> NTSpecificRights:
    return NTSpecificRights(int(access_mask & NTStoredAccessMask.SPECIFIC_RIGHTS_MASK))


def _init_reader(raw_data: Union[bytes, BinaryReader]) -> BinaryReader:
    if isinstance(raw_data, BinaryReader):
        return raw_data
    else:
        return BinaryReader(raw_data, big_endian=False)


def _decode_acl_entry(raw_type: int, raw_flags: int, ace_data: bytes) -> NTAclEntry:
    raw_type, with_object, with_callback = _ACE_TYPE_FOLD_LOOKUP.get(raw_type, (raw_type, False, False))

    if raw_type not in _SUPPORTED_ACE_TYPES:
        raise NotImplementedError(f"Don't know how to parse ACL entry of type {raw_type}")

    flags = NTAclEntryFlags(raw_flags)
    inherit_flags = decode_nt_ace_inherit_flags(flags)

    reader = _init_reader(ace_data)
    raw_access_mask = reader.read_uint32("access mask")

    object_type = None
    inherited_object_type = None
    if with_object:
        obj_flags = NTObjectSpecificACLFlags(reader.read_uint32("object flags"))
        if NTObjectSpecificACLFlags.HAS_OBJECT_TYPE in obj_flags:
            object_type = decode_nt_guid(reader)
        if NTObjectSpecificACLFlags.HAS_INHERITED_OBJECT_TYPE in obj_flags:
            inherited_object_type = decode_nt_guid(reader)

    trustee = decode_nt_security_id(reader)

    callback_data = None
    if with_callback:
        callback_data = reader.read_remainder()

    access_mask = NTStoredAccessMask(raw_access_mask)
    standard_rights = decode_nt_standard_rights(access_mask)
    specific_rights = decode_nt_specific_rights(access_mask)

    if raw_type == NTAclEntryType.ACCESS_ALLOWED:
        return NTAllowAccessACLEntry(
            trustee=trustee, inherit=inherit_flags, standard_rights=standard_rights, specific_rights=specific_rights,
            object_type=object_type, inherited_object_type=inherited_object_type, callback_data=callback_data
        )
    elif raw_type == NTAclEntryType.ACCESS_DENIED:
        return NTDenyAccessACLEntry(
            trustee=trustee, inherit=inherit_flags, standard_rights=standard_rights, specific_rights=specific_rights,
            object_type=object_type, inherited_object_type=inherited_object_type, callback_data=callback_data
        )
    elif raw_type == NTAclEntryType.SYSTEM_AUDIT:
        return NTSystemAuditACLEntry(
            trustee=trustee, inherit=inherit_flags,
            audit_success=NTAclEntryFlags.SUCCESSFUL_ACCESS in flags,
            audit_failure=NTAclEntryFlags.FAILED_ACCESS in flags,
            standard_audited_ops=standard_rights, specific_audited_ops=specific_rights,
            audit_sacl=NTStoredAccessMask.ACCESS_SYSTEM_SECURITY in access_mask,
            object_type=object_type, inherited_object_type=inherited_object_type,
            callback_data=callback_data
        )
    elif raw_type == NTAclEntryType.SYSTEM_ALARM:
        return NTSystemAlarmACLEntry(
            trustee=trustee, inherit=inherit_flags, standard_audited_ops=standard_rights,
            specific_audited_ops=specific_rights, object_type=object_type, inherited_object_type=inherited_object_type,
            callback_data=callback_data
        )
    elif raw_type == NTAclEntryType.SYSTEM_MANDATORY_LABEL:
        policy = NTMandatoryAccessPolicy(raw_access_mask)

        return NTMandatoryLabelACLEntry(
            trustee=trustee, inherit=inherit_flags,
            no_write_up=NTMandatoryAccessPolicy.NO_WRITE_UP in policy,
            no_read_up=NTMandatoryAccessPolicy.NO_READ_UP in policy,
            no_execute_up=NTMandatoryAccessPolicy.NO_EXECUTE_UP in policy,
        )

    raise NotImplementedError(f"No code to decode ACL entry of type {raw_type}")


_ACE_TYPE_FOLD_LOOKUP = {
    NTAclEntryType.ACCESS_ALLOWED_OBJECT: (NTAclEntryType.ACCESS_ALLOWED, True, False),
    NTAclEntryType.ACCESS_DENIED_OBJECT: (NTAclEntryType.ACCESS_DENIED, True, False),
    NTAclEntryType.SYSTEM_AUDIT_OBJECT: (NTAclEntryType.SYSTEM_AUDIT, True, False),
    NTAclEntryType.SYSTEM_ALARM_OBJECT: (NTAclEntryType.SYSTEM_ALARM, True, False),
    NTAclEntryType.ACCESS_ALLOWED_CALLBACK: (NTAclEntryType.ACCESS_ALLOWED, False, True),
    NTAclEntryType.ACCESS_DENIED_CALLBACK: (NTAclEntryType.ACCESS_DENIED, False, True),
    NTAclEntryType.SYSTEM_AUDIT_CALLBACK: (NTAclEntryType.SYSTEM_AUDIT, False, True),
    NTAclEntryType.SYSTEM_ALARM_CALLBACK: (NTAclEntryType.SYSTEM_ALARM, False, True),
    NTAclEntryType.ACCESS_ALLOWED_CALLBACK_OBJECT: (NTAclEntryType.ACCESS_ALLOWED, True, True),
    NTAclEntryType.ACCESS_DENIED_CALLBACK_OBJECT: (NTAclEntryType.ACCESS_DENIED, True, True),
    NTAclEntryType.SYSTEM_AUDIT_CALLBACK_OBJECT: (NTAclEntryType.SYSTEM_AUDIT, True, True),
    NTAclEntryType.SYSTEM_ALARM_CALLBACK_OBJECT: (NTAclEntryType.SYSTEM_ALARM, True, True),
}


_SUPPORTED_ACE_TYPES = {
    NTAclEntryType.ACCESS_ALLOWED, NTAclEntryType.ACCESS_DENIED, NTAclEntryType.SYSTEM_AUDIT,
    NTAclEntryType.SYSTEM_ALARM, NTAclEntryType.SYSTEM_MANDATORY_LABEL,
}
