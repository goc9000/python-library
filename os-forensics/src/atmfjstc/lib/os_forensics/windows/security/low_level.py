"""
Enums and flags that are useful during binary parsing but rarely used otherwise.
"""

from enum import IntFlag, IntEnum


class NTSdControlFlags(IntFlag):
    OWNER_DEFAULTED = 0x0001
    GROUP_DEFAULTED = 0x0002

    DACL_PRESENT = 0x0004
    DACL_DEFAULTED = 0x0008

    SACL_PRESENT = 0x0010
    SACL_DEFAULTED = 0x0020

    DACL_AUTO_INHERIT_REQ = 0x0100
    SACL_AUTO_INHERIT_REQ = 0x0200
    DACL_AUTO_INHERITED = 0x0400
    SACL_AUTO_INHERITED = 0x0800
    DACL_PROTECTED = 0x1000
    SACL_PROTECTED = 0x2000

    RM_CONTROL_VALID = 0x4000
    SELF_RELATIVE = 0x8000


class NTAclEntryType(IntEnum):
    ACCESS_ALLOWED = 0x00
    ACCESS_DENIED = 0x01
    SYSTEM_AUDIT = 0x02
    SYSTEM_ALARM = 0x03
    ACCESS_ALLOWED_COMPOUND = 0x04
    ACCESS_ALLOWED_OBJECT = 0x05
    ACCESS_DENIED_OBJECT = 0x06
    SYSTEM_AUDIT_OBJECT = 0x07
    SYSTEM_ALARM_OBJECT = 0x08
    ACCESS_ALLOWED_CALLBACK = 0x09
    ACCESS_DENIED_CALLBACK = 0x0a
    ACCESS_ALLOWED_CALLBACK_OBJECT = 0x0b
    ACCESS_DENIED_CALLBACK_OBJECT = 0x0c
    SYSTEM_AUDIT_CALLBACK = 0x0d
    SYSTEM_ALARM_CALLBACK = 0x0e
    SYSTEM_AUDIT_CALLBACK_OBJECT = 0x0f
    SYSTEM_ALARM_CALLBACK_OBJECT = 0x10
    SYSTEM_MANDATORY_LABEL = 0x11
    SYSTEM_RESOURCE_ATTRIBUTE = 0x12
    SYSTEM_SCOPED_POLICY_ID = 0x13
    SYSTEM_PROCESS_TRUST_LABEL = 0x14


class NTAclEntryFlags(IntFlag):
    OBJECT_INHERIT = 0x01
    CONTAINER_INHERIT = 0x02
    NO_PROPAGATE_INHERIT = 0x04
    INHERIT_ONLY = 0x08
    INHERITED = 0x10
    SUCCESSFUL_ACCESS = 0x40
    FAILED_ACCESS = 0x80


class NTObjectSpecificACLFlags(IntFlag):
    HAS_OBJECT_TYPE = 0x01
    HAS_INHERITED_OBJECT_TYPE = 0x02


class NTStoredAccessMask(IntFlag):
    """
    This represents a Windows NT ACCESS_MASK as it may be stored in an ACL. This means bits that only make sense during
    an access request, such as GENERIC_READ/WRITE etc. or MAXIMUM_ALLOWED, are not part of the specification. Specific
    access rights are also not defined, rather we leave this to other enums.
    """

    # Standard rights
    DELETE = 0x00010000
    READ_CONTROL = 0x00020000
    WRITE_DACL = 0x00040000
    WRITE_OWNER = 0x00080000
    SYNCHRONIZE = 0x00100000

    # Valid in system audit ACL entries (for auditing access to the SACL itself)
    ACCESS_SYSTEM_SECURITY = 0x01000000

    # Masks etc.
    STANDARD_RIGHTS_MASK = 0x001f0000
    SPECIFIC_RIGHTS_MASK = 0x0000ffff


class NTMandatoryAccessPolicy(IntFlag):
    NO_WRITE_UP = 0x0001
    NO_READ_UP = 0x0002
    NO_EXECUTE_UP = 0x0004
