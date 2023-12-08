import asyncio

from abc import ABC, abstractmethod

from .socket import UnixServerSocketConfig, setup_unix_socket


class AsyncProtocolServerBase(ABC):
    """
    Base class for other mechanisms that enable the daemon to open a socket and execute requests received there
    according to a protocol.
    """

    _server = None
    _socket_config: UnixServerSocketConfig

    _buffer_limit: int = 64 * 1024

    _request_tasks: set[asyncio.Task]

    def __init__(self, socket_config: UnixServerSocketConfig):
        """
        Constructor.

        Args:
            socket_config:
              The configuration for the socket on which the daemon will listen for requests
        """
        self._socket_config = socket_config

        self._request_tasks = set()

    async def start(self):
        """
        Initializes the socket. This is an opportunity for any major socket/permissions issues to be reported before
        the daemon main loop starts.
        """
        self._server = await asyncio.start_unix_server(
            self._on_connection_wrapper, path=self._socket_config.path, limit=self._buffer_limit
        )

        setup_unix_socket(self._socket_config)

    async def run(self, wait_requests_end: bool = True):
        """
        This runnable should be used for the async task that runs continuously and serves requests.

        Args:
            wait_requests_end:
                If true (the default), ensures that all requests have completely finished processing when this function
                returns. Normally, when the server is cancelled, the asyncio framework also cancels any pending
                request threads; however, it does not automatically wait for them to actually finish, and there are
                situations where the tasks might take a while to finish after cancellation.
        """
        try:
            async with self._server:
                await self._server.serve_forever()
        finally:
            if wait_requests_end:
                tasks_to_end = list(self._request_tasks)  # MUST make dupe of the set, as it will change during iteration
                # They should already be canceled, but just to be sure...
                for task in tasks_to_end:
                    task.cancel()
                for task in tasks_to_end:
                    try:
                        await task
                    except:
                        pass  # TODO: should probably do something here if there is an uncaught exception in the tasks
                              # (or maybe catch it in _on_connection_wrapper?)

            self._socket_config.path.unlink()

    async def _on_connection_wrapper(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._request_tasks.add(asyncio.current_task())

        try:
            await self._on_connection(reader, writer)
        finally:
            self._request_tasks.remove(asyncio.current_task())

    @abstractmethod
    async def _on_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        raise NotImplementedError
