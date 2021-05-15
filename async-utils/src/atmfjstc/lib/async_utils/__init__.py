import asyncio
import queue

from typing import Callable, Awaitable, TypeVar, Any


T = TypeVar('T')


async def run_cancelable_thread(thread_main: Callable[[], T], on_cancel: Callable[[], None]) -> Awaitable[T]:
    """
    Runs code in a separate thread, while in an async context, like `asyncio.to_thread`, but supporting task
    cancellation.

    Args:
        thread_main: The code to execute in a different thread
        on_cancel: A callback that will be called when the task is cancelled. BEWARE! This will be called in a
            different thread to that of `thread_main`, so it should only work with thread-safe objects so as to signal
            the thread to stop, e.g. by putting some element in a thread-safe queue.

    Returns:
        The result of the code in `thread_main`
    """
    thread_task = None

    try:
        thread_task = asyncio.create_task(asyncio.to_thread(thread_main))
        return await asyncio.shield(thread_task)
    except asyncio.CancelledError:
        on_cancel()

        if thread_task is not None:
            await thread_task

        raise


async def run_cancelable_thread_using_queue(
    thread_main: Callable[[queue.Queue], T], end_element: Any = None
) -> Awaitable[T]:
    """
    Runs code in a separate thread, while in an async context, like `asyncio.to_thread`, but supporting task
    cancellation. Unlike the basic `run_cancelable_thread`, this implements a specific stop signaling mechanism using
    a queue.

    Args:
        thread_main: The code to execute in a different thread. It will receive as its sole argument a queue that will
            have a value pushed to it when the cancelation of the thread is desired. Note that the thread can use the
            queue for pushing and processing its own events as well.
        end_element: The value that is pushed to the queue when it is time to stop

    Returns:
        The result of the code in `thread_main`
    """
    q = queue.Queue()

    def _thread_main():
        return thread_main(q)

    def _on_cancel():
        q.put_nowait(end_element)

    return await run_cancelable_thread(_thread_main, _on_cancel)
