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
