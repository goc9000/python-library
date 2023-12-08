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


def setup_unix_socket(socket_config: UnixServerSocketConfig):
    """
    Sets up the permissions and owner for a created Unix socket, in accordance with the configuration.

    Args:
        socket_config: The configuration of the socket
    """
    permissions = 0o600
    owner_to_set = socket_config.owner

    etg = socket_config.expose_to_group
    expose_group, group_to_set = (etg, None) if etg.__class__ == bool else (True, etg)

    if expose_group:
        permissions |= 0o060
    if socket_config.expose_to_others:
        permissions |= 0o006

    socket_config.path.chmod(permissions)

    if (owner_to_set is not None) or (group_to_set is not None):
        shutil.chown(socket_config.path, user=owner_to_set, group=group_to_set)
