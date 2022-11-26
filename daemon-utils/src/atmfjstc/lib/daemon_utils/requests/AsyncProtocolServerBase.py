import asyncio
import shutil

from pathlib import Path

from typing import Union

from abc import ABC, abstractmethod


class AsyncProtocolServerBase(ABC):
    """
    Base class for other mechanisms that enable the daemon to open a socket and execute requests received there
    according to a protocol.
    """

    _server = None
    _socket_path: Path
    _expose_to_group: Union[int, str, bool]
    _expose_to_others: bool

    _buffer_limit: int = 64 * 1024

    def __init__(
        self, socket_path: Path,
        expose_to_group: Union[bool, int, str] = False,
        expose_to_others: bool = False,
    ):
        """
        Constructor.

        Args:
            socket_path:
              Path to the socket that will be exposed for communication (e.g. `/run/daemon_name.sock`)
            expose_to_group:
              True to allow the default group access to the socket. Specify an explicit ID or name to also change the
              socket to this group (needs root access or for the daemon user to be part of that group)
            expose_to_others:
              True to allow non-owner, non-group users access to the socket
        """
        self._socket_path = socket_path
        self._expose_to_group = expose_to_group
        self._expose_to_others = expose_to_others

    async def start(self):
        """
        Initializes the socket. This is an opportunity for any major socket/permissions issues to be reported before
        the daemon main loop starts.
        """
        self._server = await asyncio.start_unix_server(
            self._on_connection, path=self._socket_path, limit=self._buffer_limit
        )

        permissions = 0o600

        etg = self._expose_to_group
        expose, group_id = (etg, None) if etg.__class__ == bool else (True, etg)

        if expose:
            permissions |= 0o060

            if group_id is not None:
                shutil.chown(self._socket_path, group=group_id)

        if self._expose_to_others:
            permissions |= 0o006

        self._socket_path.chmod(permissions)

    async def run(self):
        """
        This runnable should be used for the async task that runs continuously and serves requests.
        """
        try:
            async with self._server:
                await self._server.serve_forever()
        finally:
            self._socket_path.unlink()

    @abstractmethod
    async def _on_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        raise NotImplementedError
