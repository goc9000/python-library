import asyncio
import queue

from typing import Callable, Awaitable, TypeVar, Any


T = TypeVar('T')


async def gather_hard(*awaitables: Awaitable) -> list:
    """
    Like `asyncio.gather`, but ensures that all awaitables are canceled and waited for before the function returns.
    Thus, we can rely on the fact that once this function has returned, none of the tasks are executing anymore.

    Args:
        *awaitables: The awaitable objects to run concurrently (Tasks, coroutines, futures etc)

    Returns:
        A list with all the results of the awaitables, in order (if none was canceled or errored out)
    """
    futures = []
    try:
        conversion_error = None

        # We convert them one by one. Keep in mind that some of them might be already scheduled tasks!
        for item in awaitables:
            try:
                futures.append(asyncio.ensure_future(item))
            except Exception as e:
                if conversion_error is not None:
                    conversion_error = e

        if conversion_error is not None:
            raise conversion_error

        return await asyncio.gather(*futures, return_exceptions=False)
    finally:
        futures = [fu for fu in futures if not fu.done()]

        for item in futures:
            item.cancel()

        if len(futures) > 0:
            await asyncio.gather(*futures, return_exceptions=True)


async def run_uncancelable_thread(thread_main: Callable[[], T]) -> T:
    """
    Runs non-async code in a separate thread, while in an async context, like `asyncio.to_thread`, but with better
    behavior on cancellation.

    Specifically, if `run_uncancelable_thread` is canceled, it will wait until the thread has finished before
    acknowledging the cancellation. Thus, the thread code is guaranteed not to be running at the end of `await
    run_uncancelable_thread`. This contrasts with the default behavior of `asyncio.to_thread` which just leaves
    the thread running.

    Since the code running in the thread is not notified in any way about the cancelation, this should ideally be used
    only for operations that take a short, well-bound time, and/or cannot be safely interrupted.

    Args:
        thread_main: The non-async code to execute in a different thread

    Returns:
        The result of the code in `thread_main`
    """
    # Could just call run_cancelable_thread with a blank on_cancel= parameter, but let's avoid adding more confusion
    # to the stack trace...

    thread_task = None

    try:
        thread_task = asyncio.create_task(asyncio.to_thread(thread_main))
        return await asyncio.shield(thread_task)
    except asyncio.CancelledError:
        if thread_task is not None:
            await thread_task

        raise


async def run_cancelable_thread(thread_main: Callable[[], T], on_cancel: Callable[[], None]) -> T:
    """
    Runs non-async code in a separate thread, while in an async context, like `asyncio.to_thread`, but supporting a
    generic mechanism for canceling the code in the thread.

    Specifically, if `run_cancelable_thread` is canceled, it will run the callback in `on_cancel=`, which can then
    signal the code in the thread to terminate, e.g. by putting some element in a queue, triggering an Event etc. The
    sync code must of course be designed to cooperate. BEWARE: `on_cancel` will always be called in a different thread
    to that of `thread_main`, so it should only work with thread-safe objects.

    In any case, `run_cancelable_thread` will wait for the sync code to completely finish executing before returning
    itself, either normally or by propagating the cancelation.

    Args:
        thread_main: The code to execute in a different thread
        on_cancel: A callback that will be called when the task is cancelled, so as to stop the thread. Please check the
            function description for details and caveats.

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
) -> T:
    """
    Runs code in a separate thread, while in an async context, like `asyncio.to_thread`, but supporting a specific,
    queue-based mechanism for canceling the code in the thread.

    See `run_cancelable_thread` for details on the general caveats and semantics of running cancelable sync code.

    Args:
        thread_main: The code to execute in a different thread. It will receive as its sole argument a thread-safe queue
            that will have a value pushed to it when the cancelation of the thread is desired. Note that the thread may
            use the queue for pushing and processing its own events as well.
        end_element: The value that is pushed to the queue when it is time to stop (default `None`)

    Returns:
        The result of the code in `thread_main`
    """
    q = queue.Queue()

    def _thread_main():
        return thread_main(q)

    def _on_cancel():
        q.put_nowait(end_element)

    return await run_cancelable_thread(_thread_main, _on_cancel)
