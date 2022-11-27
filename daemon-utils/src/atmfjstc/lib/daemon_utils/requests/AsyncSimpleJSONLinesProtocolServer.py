import asyncio
import logging
import json
import re

from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional, Union

from atmfjstc.lib.daemon_utils.requests.standard_errors import BasicError, InternalError, RequestNotJSONError, \
    RequestTooLargeError, DaemonShuttingDownError
from atmfjstc.lib.daemon_utils.requests.AsyncProtocolServerBase import AsyncProtocolServerBase


LOG = logging.getLogger()


@dataclass(frozen=True)
class MicroResponse:
    """
    Special class for enabling more advanced request processing such as binary uploads and downloads. The following
    parameters are available:

    `reply`:
      A dict containing the response that should be sent immediately after the request is received (and before any
      binary uploads are processed as well as before any downloads occur). May be None, in which case no response will
      be sent at this point, but this is not recommended - for symmetry, both downloads and uploads should feature a
      preliminary response signaling whether the download or upload can proceed.

    `serve_download`:
      If provided, this async callable will be called with a `StreamWriter` where the binary data for the download is to
      be written (e.g. by a closure inside the request processing function). If the async callable returns a dict, this
      reply will be written to the socket after the download (e.g. for announcing a checksum). Any errors during the
      download will cause the stream to be broken off abruptly - a JSON error will never be emitted in the case.

    `receive_upload`:
      If provided, this async callable will be called with a `StreamReader` where the binary data for any upload can be
      read (e.g. by a closure inside the request processing function). It is up to the caller to know how much to read.
      The same considerations regarding a final response and the handling of errors apply as for the `serve_download`
      callback.

    `multi_reply`:
      If provided, this async callable will be called with another async callable that can be used so as to continue
      emitting replies after the first one over time, e.g. to implement a long polling or subscription feature. Note
      that if the peer closes the connection (even just their write side), the callable will be cancelled. Also, for
      simplicitly, any further input sent by the peer is ignored - closing the connection is the only event we listen
      for.

    `cleanup`:
      If provided, this async callable will be awaited for, no matter what, once the response has been served. It is
      meant to be used as a cleanup stage for any resources temporarily allocated for serving a download/upload
      response.

    The order of processing is:

    - the JSON part of the request is obtained from the user
    - `reply` is emitted (if not None)
    - `receive_upload` is called and its response emitted (if not None)
    - `server_download` is called and its response emitted (if not None)
    - `multi_reply` is called, if applicable
    - `cleanup` is called (if not None)
    """

    reply: Optional[dict] = None
    serve_download: Optional[Callable[[asyncio.StreamWriter], Awaitable[Optional[dict]]]] = None
    receive_upload: Optional[Callable[[asyncio.StreamReader], Awaitable[Optional[dict]]]] = None
    multi_reply: Optional[Callable[[Callable[[dict], Awaitable[None]]], Awaitable[None]]] = None
    cleanup: Optional[Callable[[], Awaitable[None]]] = None

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

    To report an error back to the caller, you can return an appropriate response or just throw. By default, this server
    will format all exceptions it doesn't recognize as "Internal error", but you add specific handling for any other
    exception and also control how exceptions are converted to responses.

    Although this server is mostly meant for basic, "single request, single reply" scenarios, some more advanced
    features (binary uploads/downloads, long polling, subscription etc) are available by returning a `MicroResponse`
    object instead of a dict (see the `MicroResponse` class for details).

    Notes:

    - Requests are handled independently. If there is any need to ensure that only one request is executing at any
      given time, or some other locking, this should be done by the caller in the request handler
    - This just ensures the basic JSON format is respected, any more advanced encoding/decoding/schema checking is
      up to the caller
    """

    _request_handler: Callable[[dict], Awaitable[Union[dict, MicroResponse]]]
    _error_response_hook: Callable[[Exception], Optional[dict]]
    _keep_connection_open: bool
    _max_request_size: int

    def __init__(
        self, socket_path: Path,
        request_handler: Callable[[dict], Awaitable[Union[dict, MicroResponse]]],
        expose_to_group: Union[bool, int, str] = False,
        expose_to_others: bool = False,
        format_error: Optional[Callable[[Exception], Optional[dict]]] = None,
        keep_connection_open: bool = False,
        max_request_size: int = 128 * 1024,
    ):
        """
        Constructor.

        Args:
            socket_path:
              Path to the socket that will be exposed for communication (e.g. `/run/daemon_name.sock`)
            request_handler:
              An async function that will be called with a dict representing the request. It must return a dict
              containing the response (or a `MicroResponse` for more advanced situations, check the class
              documentation).
            expose_to_group:
              True to allow the default group access to the socket. Specify an explicit ID or name to also change the
              socket to this group (needs root access or for the daemon user to be part of that group)
            expose_to_others:
              True to allow non-owner, non-group users access to the socket
            format_error:
              Specify a function here to customize how exceptions are converted to responses. The function will receive
              an Exception and must return a dict with the response. If you return None, the default processing will be
              performed.
            keep_connection_open:
              If set to true, the connection will remain open after a request is executed, allowing the client to send
              more requests. The connection will still close after any error that is likely to cause loss of sync (e.g.
              malformed JSON)
            max_request_size:
              The maximum request size, in bytes
        """
        super().__init__(socket_path=socket_path, expose_to_group=expose_to_group, expose_to_others=expose_to_others)

        self._request_handler = request_handler
        self._error_response_hook = format_error
        self._keep_connection_open = keep_connection_open
        self._max_request_size = max_request_size

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
            response, _ = self._format_error_response(error)
            await self._reply_best_effort(writer, response)
            return False

        if request is None:
            return False

        try:
            response = await self._request_handler(request)
        except Exception as error:
            if isinstance(error, asyncio.CancelledError):
                error = DaemonShuttingDownError()

            response, caller_handled = self._format_error_response(error)

            if not isinstance(error, BasicError) and not caller_handled:
                logging.exception("Unexpected exception while processing request")

            await self._reply_best_effort(writer, response)
            return False

        response = MicroResponse.normalize(response)

        try:
            can_continue = await self._serve_response(response, reader, writer)
        finally:
            if response.cleanup is not None:
                try:
                    await response.cleanup()
                except asyncio.CancelledError:
                    can_continue = False
                except Exception:
                    logging.exception("Unexpected exception while cleaning up")
                    can_continue = False

        return can_continue

    async def _serve_response(
        self, response: MicroResponse, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> bool:
        reply_ok = await self._reply_best_effort(writer, response.reply)
        if not reply_ok:
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
            except Exception:
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
            except Exception:
                logging.exception("Unexpected exception while serving download")
                return False

        if response.multi_reply is not None:
            try:
                await self._serve_multi_reply(response.multi_reply, reader, writer)
            except asyncio.CancelledError:
                return False
            except Exception:
                logging.exception("Unexpected exception while serving multiple responses")
                return False

        return True

    async def _serve_multi_reply(
        self,
        user_code: Optional[Callable[[Callable[[dict], Awaitable[None]]], Awaitable[None]]],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        done_event = asyncio.Event()

        async def _write_cb(response: dict):
            success = await self._reply_best_effort(writer, response)
            if not success:
                done_event.set()

        async def _actual_task():
            try:
                await user_code(_write_cb)
            finally:
                done_event.set()

        async def _wait_eof():
            try:
                while True:
                    data = await reader.read(65536)
                    if data == b'':
                        break
            except:
                pass

            done_event.set()

        user_code_real_task = asyncio.create_task(_actual_task())
        wait_eof_task = asyncio.create_task(_wait_eof())

        my_cancelation = None
        try:
            await done_event.wait()
        except asyncio.CancelledError as e:
            my_cancelation = e

        user_code_real_task.cancel()
        wait_eof_task.cancel()

        try:
            await asyncio.shield(user_code_real_task)
        except asyncio.CancelledError as e:
            my_cancelation = e

        # We don't wait for the wait_eof() task to finish, it has no effects and terminates immediately anyway

        if my_cancelation is not None:
            raise my_cancelation

    async def _read_request(self, reader: asyncio.StreamReader) -> Optional[dict]:
        try:
            finished = False
            parts = []
            total_len = 0

            while not finished:
                try:
                    data = await reader.readuntil(b'\n')
                    finished = True
                except asyncio.LimitOverrunError:
                    data = await reader.readexactly(self._buffer_limit)
                except asyncio.IncompleteReadError as e:
                    data = e.partial
                    finished = True

                if len(parts) == 0:
                    if data == b'':
                        return None
                    if not re.match(rb'\s*{', data):
                        raise RequestNotJSONError

                parts.append(data)
                total_len += len(data)

                if total_len > self._max_request_size:
                    raise RequestTooLargeError(self._max_request_size)
        except asyncio.CancelledError:
            raise DaemonShuttingDownError from None
        except (RequestTooLargeError, RequestNotJSONError):
            raise
        except Exception:
            logging.exception("Unexpected exception while reading request")
            raise InternalError from None

        data = b''.join(parts)

        try:
            request = json.loads(data)
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

    def _format_error_response(self, error: Exception) -> tuple[dict, bool]:
        if self._error_response_hook is not None:
            try:
                response = self._error_response_hook(error)

                if response is not None:
                    return response, True
            except:
                return self._format_error_fallback(InternalError()), False

        return self._format_error_fallback(error), False

    def _format_error_fallback(self, error: Exception) -> dict:
        if not isinstance(error, BasicError):
            error = InternalError()

        params = dict(
            status='error',
            code=error.code.value,
            message=error.args[0],
        )

        if isinstance(error, RequestTooLargeError):
            params['max_size'] = error.max_size

        return params
