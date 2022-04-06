import asyncio
import logging
import json

from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional, Union, Literal

from atmfjstc.lib.daemon_utils.requests.standard_errors import BasicError, InternalError, RequestNotJSONError, \
    RequestTooLargeError, DaemonShuttingDownError
from atmfjstc.lib.daemon_utils.requests.AsyncProtocolServerBase import AsyncProtocolServerBase


LOG = logging.getLogger()


@dataclass(frozen=True)
class MicroResponse:
    """
    Special class for enabling more advanced request processing such as binary uploads and downloads. The following
    parameters are available:

    - `reply`: A dict containing the response that should be sent immediately after the request is received (and
               before any binary uploads are processed as well as before any downloads occur). May be None, in which
               case no response will be sent at this point, but this is not recommended - for symmetry, both downloads
               and uploads should feature a preliminary response signaling whether the download or upload can proceed.
    - `serve_download`: If provided, this async callable will be called with a `StreamWriter` where the binary data
                        for the download is to be written (e.g. by a closure inside the request processing function).
                        If the async callable returns a dict, this reply will be written to the socket after the
                        download (e.g. for announcing a checksum). Any errors during the download will cause the stream
                        to be broken off abruptly - a JSON error will never be emitted in the case.
    - `receive_upload`: If provided, this async callable will be called with a `StreamReader` where the binary data for
                        any upload can be read (e.g. by a closure inside the request processing function). It is up to
                        the caller to know how much to read. The same considerations regarding a final response and
                        the handling of errors apply as for the `serve_download` callback.

    The order of processing is:

    - the JSON part of the request is obtained from the user
    - `reply` is emitted (if not None)
    - `receive_upload` is called and its response emitted (if not None)
    - `server_download` is called and its response emitted (if not None)
    """

    reply: Optional[dict] = None
    serve_download: Optional[Callable[[asyncio.StreamWriter], Awaitable[Optional[dict]]]] = None
    receive_upload: Optional[Callable[[asyncio.StreamReader], Awaitable[Optional[dict]]]] = None

    @staticmethod
    def normalize(response: Union[dict, 'MicroResponse']) -> 'MicroResponse':
        return response if isinstance(response, MicroResponse) else MicroResponse(reply=response)


class AsyncSimpleJSONLinesProtocolServer(AsyncProtocolServerBase):
    """
    Main task for an async daemon that enables it to respond to requests issued over a socket, in "JSON lines" format.

    Specifically, each request, as well as its response, is expected to be valid JSON terminated by a newline, with no
    newlines inside (encoded newlines in strings are OK of course).

    The simplest use of this is along the lines of::

        server = AsyncSimpleJSONLinesProtocolServer(socket_path=..., request_handler=_my_request_func)

        async def _my_request_func(request: dict) -> dict:
            # Return appropriate response dict here

        # (call await server.start() and then await server.run() in the daemon main loop)

    For more advanced processing, you can also subclass this.

    This server also supports a simple mechanism for large binary uploads/downloads. To make use of it, return a
    `MicroResponse` class instead of a dict (see the `MicroResponse` class docs for details on how to handle uploads/
    downloads)

    Notes:

    - Requests are handled independently. If there is any need to ensure that only one request is executing at any
      given time, or some other locking, this should be done by the caller in the request handler
    - This just ensures the basic JSON format is respected, any more advanced encoding/decoding/schema checking is
      up to the caller
    - Only a basic, "single request", "single response" interaction is implemented (no long polling, etc)
    """

    _request_handler: Callable[[dict], Awaitable[Union[dict, MicroResponse]]]
    _error_response_hook: Callable[[Exception], Optional[dict]]
    _keep_connection_open: bool

    def __init__(
        self, socket_path: Path,
        request_handler: Callable[[dict], Awaitable[Union[dict, MicroResponse]]],
        expose_to_group: Union[bool, int, str] = False,
        expose_to_others: bool = False,
        format_error: Optional[Callable[[Exception], Optional[dict]]] = None,
        keep_connection_open: bool = False,
    ):
        """
        Constructor.

        Args:
            socket_path: Path to the socket that will be exposed for communication (e.g. `/run/daemon_name.sock`)
            request_handler: An async function that will be called with a dict representing the request. It must
                             return a dict containing the response (or a MicroResponse for more advanced situations,
                             check the class documentation).
            expose_to_group: True to allow the default group access to the socket. Specify an explicit ID or name to
                             also change the socket to this group (needs root access or for the daemon user to be part
                             of that group)
            expose_to_others: True to allow non-owner, non-group users access to the socket
            format_error: Specify a function here to customize how exceptions are converted to responses. The function
                          will receive an Exception and must return a dict with the response. If you return None, the
                          default processing will be performed.
            keep_connection_open: If set to true, the connection will remain open after a request is executed, allowing
                                  the client to send more requests. The connection will still close after any error that
                                  is likely to cause loss of sync (e.g. malformed JSON)
        """
        super().__init__(socket_path=socket_path, expose_to_group=expose_to_group, expose_to_others=expose_to_others)

        self._request_handler = request_handler
        self._error_response_hook = format_error
        self._keep_connection_open = keep_connection_open

    async def _on_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                can_continue = await self._read_request_loop(reader, writer)
                if not can_continue or not self._keep_connection_open:
                    break
        except:
            logging.exception("Unexpected exception while handling connection")
        finally:
            # Swallow errors as we may get BrokenPipe
            try:
                writer.close()
            except:
                pass
            try:
                await writer.wait_closed()
            except:
                pass

    async def _read_request_loop(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        try:
            request = await self._read_request(reader)
        except Exception as error:
            response = self._format_error_response(error)
            await self._reply_best_effort(writer, response)
            return False

        if request is None:
            return False

        can_continue = True
        try:
            response = await self._request_handler(request)
        except asyncio.CancelledError:
            response = self._shutting_down_error_response()
            can_continue = False
        except:
            logging.exception("Unexpected exception while processing request")
            response = self._internal_error_response()

        response = MicroResponse.normalize(response)

        reply_ok = await self._reply_best_effort(writer, response.reply)
        if not reply_ok or not can_continue:
            return False

        if response.receive_upload is not None:
            try:
                second_response = await response.receive_upload(reader)
                if not await self._reply_best_effort(writer, second_response):
                    return False
            except asyncio.CancelledError:
                # Note that we intentionally don't send error responses during the upload as we don't know whether the
                # client expects multiple JSON replies. The serve_download callback can be made to intercept these
                # errors and send a specific response if desired.
                return False
            except:
                logging.exception("Unexpected exception while reading upload")
                return False

        if response.serve_download is not None:
            try:
                second_response = await response.serve_download(writer)
                await writer.drain()
                if not await self._reply_best_effort(writer, second_response):
                    return False
            except asyncio.CancelledError:
                return False
            except:
                logging.exception("Unexpected exception while serving download")
                return False

        return True

    async def _read_request(self, reader: asyncio.StreamReader) -> Optional[dict]:
        try:
            line = await reader.readuntil(b'\n')
        except asyncio.LimitOverrunError:
            raise RequestTooLargeError
        except asyncio.IncompleteReadError as e:
            line = e.partial
        except asyncio.CancelledError:
            raise DaemonShuttingDownError
        except Exception:
            logging.exception("Unexpected exception while reading request")
            raise InternalError

        if line == b'':
            return None

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            request = None

        if not isinstance(request, dict):
            raise RequestNotJSONError

        return request

    async def _reply_best_effort(self, writer: asyncio.StreamWriter, response: Optional[dict]) -> bool:
        if response is None:
            return True

        try:
            writer.write(json.dumps(response).encode('utf-8') + b'\n')
            await writer.drain()

            return True
        except:
            return False

    def _internal_error_response(self) -> dict:
        return self._format_error_response(InternalError())

    def _shutting_down_error_response(self) -> dict:
        return self._format_error_response(DaemonShuttingDownError())

    def _format_error_response(self, error: Exception) -> dict:
        if self._error_response_hook is not None:
            try:
                response = self._error_response_hook(error)

                if response is not None:
                    return response
            except:
                return self._format_error_fallback(InternalError())

        return self._format_error_fallback(error)

    def _format_error_fallback(self, error: Exception) -> dict:
        if not isinstance(error, BasicError):
            error = InternalError()

        return dict(
            status='error',
            code=error.code.value,
            message=error.args[0],
        )
