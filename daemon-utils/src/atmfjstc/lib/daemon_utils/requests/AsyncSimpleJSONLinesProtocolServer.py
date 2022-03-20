import asyncio
import logging
import json
import shutil

from pathlib import Path

from typing import Callable, Awaitable, Optional, Union


LOG = logging.getLogger()


class AsyncSimpleJSONLinesProtocolServer:
    """
    Main task for an async daemon that enables it to respond to requests issued over a socket, in "JSON lines" format.

    Specifically, each request, as well as its response, is expected to be valid JSON terminated by a newline, with no
    newlines inside (encoded newlines in strings are OK of course).

    Notes:
    - Requests are handled independently. If there is any need to ensure that only one request is executing at any
      given time, or some other locking, this should be done by the caller in the request handler
    - This just ensures the basic JSON format is respected, any more advanced encoding/decoding/schema checking is
      up to the caller
    - Only a basic, "single request", "single response" interaction is implemented (no long polling, etc)
    """

    _server = None
    _socket_path: Path
    _request_handler: Callable[[dict], Awaitable[dict]]
    _format_simple_error: Callable[[str], dict]
    _expose_to_group: Union[int, str, bool]
    _expose_to_others: bool

    def __init__(
        self, socket_path: Path,
        request_handler: Callable[[dict], Awaitable[dict]],
        expose_to_group: Union[bool, int, str] = False,
        expose_to_others: bool = False,
        error_response_maker: Optional[Callable[[str], dict]] = None,
    ):
        """
        Constructor.

        Args:
            socket_path: Path to the socket that will be exposed for communication (e.g. `/run/daemon_name.sock`)
            request_handler: An async function that will be called with a dict representing the request. It must
                             return a dict containing the response.
            expose_to_group: True to allow the default group access to the socket. Specify an explicit ID or name to
                             also change the socket to this group (needs root access or for the daemon user to be part
                             of that group)
            expose_to_others: True to allow non-owner, non-group users access to the socket
            error_response_maker: Use this to override the format of the response for simple protocol errors
        """
        self._socket_path = socket_path

        self._request_handler = request_handler
        self._format_simple_error = error_response_maker or _default_error_response_maker

        self._expose_to_group = expose_to_group
        self._expose_to_others = expose_to_others

    async def start(self):
        """
        Initializes the socket. This is an opportunity for any major socket/permissions issues to be reported before
        the daemon main loop starts.
        """
        self._server = await asyncio.start_unix_server(self._on_connection, path=self._socket_path)

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

    async def _on_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        response = None

        try:
            line = await reader.readline()
            if line != b'':
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    request = None

                if isinstance(request, dict):
                    response = await self._request_handler(request)
                else:
                    response = self._format_simple_error("Request is not valid one-line JSON")
        except asyncio.CancelledError:
            response = self._format_simple_error("Daemon shutting down")
            raise
        except:
            logging.exception("Unexpected exception while processing request")
            response = self._format_simple_error("Internal error")
        finally:
            if response is not None:
                try:
                    writer.write(json.dumps(response).encode('utf-8') + b'\n')
                    await writer.drain()
                except:
                    pass

            writer.close()


def _default_error_response_maker(message: str) -> dict:
    return dict(
        status='error',
        message=message,
    )
