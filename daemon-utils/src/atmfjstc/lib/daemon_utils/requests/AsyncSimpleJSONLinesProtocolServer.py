import asyncio
import logging
import json

from pathlib import Path

from typing import Callable, Awaitable, Optional, Union, Literal

from atmfjstc.lib.daemon_utils.requests.AsyncProtocolServerBase import AsyncProtocolServerBase


LOG = logging.getLogger()


class AsyncSimpleJSONLinesProtocolServer(AsyncProtocolServerBase):
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

    _request_handler: Callable[[dict], Awaitable[dict]]
    _format_simple_error: Callable[[str], dict]

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
        super().__init__(socket_path=socket_path, expose_to_group=expose_to_group, expose_to_others=expose_to_others)

        self._request_handler = request_handler
        self._format_simple_error = error_response_maker or _default_error_response_maker

    async def _on_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        response = None

        try:
            request, response = await self._read_request(reader)

            if request is not None:
                response = await self._request_handler(request)
        except asyncio.CancelledError:
            response = self._shutting_down_error_response()
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

    async def _read_request(
        self, reader: asyncio.StreamReader
    ) -> Union[tuple[dict, Literal[None]], tuple[Literal[None], Optional[dict]]]:
        try:
            line = await reader.readuntil(b'\n')
        except asyncio.LimitOverrunError:
            return None, self._format_simple_error("Request too large")
        except asyncio.IncompleteReadError as e:
            line = e.partial
        except asyncio.CancelledError:
            return None, self._shutting_down_error_response()
        except:
            logging.exception("Unexpected exception while reading request")
            return None, self._format_simple_error("Internal error")

        if line == b'':
            return None, None

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            request = None

        if isinstance(request, dict):
            return request, None

        return None, self._format_simple_error("Request is not valid one-line JSON")

    def _shutting_down_error_response(self) -> dict:
        return self._format_simple_error("Daemon shutting down")


def _default_error_response_maker(message: str) -> dict:
    return dict(
        status='error',
        message=message,
    )
