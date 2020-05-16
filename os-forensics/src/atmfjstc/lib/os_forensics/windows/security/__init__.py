from dataclasses import dataclass
from typing import Optional, Tuple

from atmfjstc.lib.os_forensics.windows.security.rights import NTSpecificRights


@dataclass(frozen=True)
class NTSecurityID:
    revision: int
    authority: int
    subauthorities: Tuple[int, ...]

    def __str__(self):
        return f"S-{self.revision}-{self.authority}{''.join('-' + str(auth) for auth in self.subauthorities)}"


@dataclass(frozen=True)
class NTGuid:
    group1: int
    group2: int
    group3: int
    group4: int
    group5: int

    def __post_init__(self):
        assert 0 <= self.group1 < (1 << 32)
        assert 0 <= self.group2 < (1 << 16)
        assert 0 <= self.group3 < (1 << 16)
        assert 0 <= self.group4 < (1 << 16)
        assert 0 <= self.group5 < (1 << 48)

    def __str__(self):
        return f"{self.group1:08X}-{self.group2:04X}-{self.group3:04X}-{self.group4:04X}-{self.group5:012X}"


@dataclass(frozen=True)
class NTSecurityDescriptor:
    owner: 'NTSdTrusteeInfo'
    group: 'NTSdTrusteeInfo'

    dacl: 'NTSdACLInfo'
    sacl: 'NTSdACLInfo'

    rm_control_valid: bool


@dataclass(frozen=True)
class NTSdTrusteeInfo:
    sid: Optional[NTSecurityID]
    defaulted: bool


@dataclass(frozen=True)
class NTSdACLInfo:
    present: bool
    null: bool
    entries: Tuple['NTAclEntry', ...]
    defaulted: bool
    auto_inherit_req: bool
    auto_inherited: bool
    protected: bool


@dataclass(frozen=True)
class NTAclEntry:
    trustee: NTSecurityID
    inherit: 'NTAclEntryInheritFlags'


@dataclass(frozen=True)
class NTAclEntryInheritFlags:
    objects: bool
    containers: bool
    no_propagate: bool
    inherit_only: bool
    inherited: bool


@dataclass(frozen=True)
class NTDiscretionaryACLEntry(NTAclEntry):
    pass


@dataclass(frozen=True)
class NTRegularDACLEntryBase(NTDiscretionaryACLEntry):
    standard_rights: 'NTStandardRights'
    specific_rights: NTSpecificRights
    object_type: Optional[NTGuid]
    inherited_object_type: Optional[NTGuid]
    callback_data: Optional[bytes]


@dataclass(frozen=True)
class NTAllowAccessACLEntry(NTRegularDACLEntryBase):
    pass


@dataclass(frozen=True)
class NTDenyAccessACLEntry(NTRegularDACLEntryBase):
    pass


@dataclass(frozen=True)
class NTSystemACLEntry(NTAclEntry):
    pass


@dataclass(frozen=True)
class NTRegularSACLEntryBase(NTSystemACLEntry):
    standard_audited_ops: 'NTStandardRights'
    specific_audited_ops: NTSpecificRights
    object_type: Optional[NTGuid]
    inherited_object_type: Optional[NTGuid]
    callback_data: Optional[bytes]


@dataclass(frozen=True)
class NTSystemAuditACLEntry(NTRegularSACLEntryBase):
    audit_success: bool
    audit_failure: bool
    audit_sacl: bool


@dataclass(frozen=True)
class NTSystemAlarmACLEntry(NTRegularSACLEntryBase):
    pass


@dataclass(frozen=True)
class NTMandatoryLabelACLEntry(NTSystemACLEntry):
    no_write_up: bool
    no_read_up: bool
    no_execute_up: bool


@dataclass(frozen=True)
class NTStandardRights:
    delete: bool
    read_control: bool
    write_dacl: bool
    write_owner: bool
    synchronize: bool
