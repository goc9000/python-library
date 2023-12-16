import shutil

from dataclasses import dataclass
from pathlib import Path

from typing import Union, Optional


@dataclass
class UnixServerSocketConfig:
    """
    Class for holding the desired configuration for a Unix socket on which a daemon listens for requests.
    """

    path: Path
    "The path to the socket."

    owner: Optional[Union[int, str]] = None
    "Specify an explicit ID or name to change the socket owner. If None the owner is unchanged."

    expose_to_group: Union[bool, int, str] = False
    """
    True to allow the default group access to the socket. Specify an explicit ID or name to also change the socket to
    this group (needs root access or for the daemon user to be part of that group).
    """

    expose_to_others: bool = False
    "Whether non-owner, non-group users have access to the socket"

    perms_fail_ok: bool = False
    """
    If true, setting permissions is done on a best-effort basis and no error will be raised if we are not able to set
    the permissions due to e.g. not being root.
    """

    owner_fail_ok: bool = False
    """
    If true, setting the owner/group is done on a best-effort basis and no error will be raised if the operation fails
    due to e.g. not being root.
    """


class UnixSocketSetupError(Exception):
    pass


class UnixSocketParentDirSetupError(UnixSocketSetupError):
    def __init__(self, message: Optional[str] = None):
        super().__init__(message or "Could not set up parent directory for daemon socket, maybe you need root access")


class UnixSocketPermissionsSetupError(UnixSocketSetupError):
    def __init__(self, message: Optional[str] = None):
        super().__init__(message or "Could not set permissions for daemon socket, maybe you need root access")


class UnixSocketOwnerSetupError(UnixSocketSetupError):
    def __init__(self, message: Optional[str] = None):
        super().__init__(message or "Could not set owner/group for daemon socket, maybe you need root access")


def pre_setup_unix_socket(socket_config: UnixServerSocketConfig):
    """
    Performs any necessary setup before a Unix socket is created. Currently this only means creating the parent
    directory if necessary.

    Args:
        socket_config: The configuration of the socket

    Raises:
        UnixSocketParentDirSetupError: If the parent directory could not be set up
    """
    try:
        socket_config.path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    except OSError:
        raise UnixSocketParentDirSetupError() from None


def setup_unix_socket(socket_config: UnixServerSocketConfig):
    """
    Sets up the permissions and owner for a created Unix socket, in accordance with the configuration.

    Args:
        socket_config: The configuration of the socket

    Raises:
        UnixSocketPermissionsSetupError: If the permissions could not be set up, unless we indicate that we tolerate
            this by setting `socket_config.perms_fail_ok`
        UnixSocketOwnerSetupError: If the owner/group could not be set up (e.g. due to not being root), unless we
            indicate that we tolerate this by setting `socket_config.owner_fail_ok`
    """
    permissions = 0o600
    owner_to_set = socket_config.owner

    etg = socket_config.expose_to_group
    expose_group, group_to_set = (etg, None) if etg.__class__ == bool else (True, etg)

    if expose_group:
        permissions |= 0o060
    if socket_config.expose_to_others:
        permissions |= 0o006

    try:
        socket_config.path.chmod(permissions)
    except PermissionError:
        if not socket_config.perms_fail_ok:
            raise UnixSocketPermissionsSetupError() from None

    if (owner_to_set is not None) or (group_to_set is not None):
        try:
            shutil.chown(socket_config.path, user=owner_to_set, group=group_to_set)
        except PermissionError:
            if not socket_config.owner_fail_ok:
                raise UnixSocketOwnerSetupError() from None
