"""
Utilities for nicely handling errors in command-line programs.
"""

import sys

from typing import NoReturn, ContextManager, List, Optional, Callable
from textwrap import dedent, indent
from functools import wraps
from contextlib import contextmanager

from atmfjstc.lib.error_utils import format_exception_head, format_exception_trace
from atmfjstc.lib.py_lang_utils.iteration import iter_with_first
from atmfjstc.lib.cli_utils.console import console


class DescriptiveError(RuntimeError):
    """
    An exception class for errors where it is clear from the message what happened and where, and the traceback is
    redundant.

    Exceptions of this kind have special handling all throughout the `cli_utils.errors` package: usually just the
    message is shown, without the trace or exception type.

    The intended use case is for when the program encounters an adverse condition and you want to immediately exit and
    display a message to the user without any other confusing details. Do NOT use this in libraries, because it is
    impossible to know ahead of time whether descriptive errors are appropriate in the context where the functions are
    used.

    When using this exception, it is recommended that the main function of the program or thread be decorated with
    `@pretty_unhandled`.
    """


def fail(message: str) -> NoReturn:
    """
    Shortcut for throwing a `DescriptiveError`. See its docs for details.
    """
    raise DescriptiveError(dedent(message).strip())


@contextmanager
def descriptive_errors(*classes: type) -> ContextManager[None]:
    """
    Use ``with descriptive_errors(Exc1, Exc2, ...): <code>`` to transform all exceptions of a given kind into
    descriptive errors.
    """
    try:
        yield
    except BaseException as e:
        for cls in e.__class__.__mro__:
            if cls in classes:
                exc = DescriptiveError(short_format_exception(e, follow_cause=False, force_descriptive=True))
                exc.__cause__ = e.__cause__

                raise exc

        raise


def pretty_print_exception(exception: BaseException, follow_cause: bool = True, force_descriptive: bool = False):
    """
    Prints an exception on the console in an intelligent and informative way.

    There is special handling for `SystemExit`, `KeyboardInterrupt` and `DescriptiveError`. For all of these, nice,
    user-friendly messages are printed. All other exceptions are assumed to be bugs and will show a full stack trace.
    """

    if isinstance(exception, SystemExit):
        # Intentionally do nothing
        return
    if isinstance(exception, KeyboardInterrupt):
        console.print_warning("Stopped by user")
        return

    if force_descriptive or isinstance(exception, DescriptiveError):
        console.print_error(
            short_format_exception(exception, follow_cause=follow_cause, force_descriptive=force_descriptive)
        )
        return

    for cause, is_first in iter_with_first(_causal_chain(exception, follow_cause=follow_cause)):
        base_indent = '' if is_first else '  '

        if not is_first:
            console.print_error("Cause:", minor=True)

        console.print_error(indent(format_exception_head(cause), base_indent))
        console.print_error(base_indent + "Traceback:", minor=True)
        console.print_error(indent(format_exception_trace(cause), base_indent + '  '), minor=True)


def short_format_exception(exception: BaseException, follow_cause: bool = True, force_descriptive: bool = False) -> str:
    """
    Presents an exception in a shorter format, e.g. for inclusion into a message.

    This is smarter than just calling `str()` on the exception. There is special handling for `SystemExit`,
    `KeyboardInterrupt` and `DescriptiveError`. For other exceptions, the class name will be printed, but not the
    trace.

    Exceptions in `__cause__` will also be followed and printed. Note that the return value may be multiline because
    of this.
    """

    if isinstance(exception, SystemExit):
        return "Program is exiting"
    if isinstance(exception, KeyboardInterrupt):
        return "User aborted operation"

    causes = _causal_chain(exception, follow_cause)

    if force_descriptive or isinstance(exception, DescriptiveError):
        head = str(exception)
        if head == '':
            head = exception.__class__.__name__

        return '\n'.join([
            head,
            # Note how a DescriptiveError suppresses trace printing for all errors that caused it, even if they are not
            # DescriptiveError's themselves. This is intentional.
            *(
                indent(short_format_exception(cause, follow_cause=False, force_descriptive=True), '  ')
                for cause in causes[1:]
            )
        ])

    return '\n'.join([
        format_exception_head(exception),
        *(indent(format_exception_head(cause), '  ') for cause in causes[1:])
    ])


def _causal_chain(exception: BaseException, follow_cause: bool) -> List[BaseException]:
    result = [exception]

    while follow_cause and exception.__cause__ is not None:
        exception = exception.__cause__
        result.append(exception)

    return result


def pretty_unhandled(on_crash: Optional[Callable[[], None]] = None) -> Callable:
    """
    Decorator for a main method that causes unhandled exceptions to be displayed in a pretty way.

    Among other things, this is necessary for the `DescriptiveError` mechanism to work.

    By default, ``sys.exit(-1)`` will be called if an exception occurs. Use the `on_crash` parameter to cause something
    else to happen (especially for threads). BEWARE! This will NOT be called for a `SystemException` or
    `KeyboardInterrupt`.
    """

    def real_decorator(main_method):
        @wraps(main_method)
        def wrapper(*args, **kwargs):
            try:
                return main_method(*args, **kwargs)
            except SystemExit:
                raise
            except KeyboardInterrupt as e:
                pretty_print_exception(e)
                sys.exit(0)
            except BaseException as e:
                pretty_print_exception(e)

            if on_crash is None:
                sys.exit(-1)
            else:
                on_crash()

        return wrapper

    return real_decorator


@contextmanager
def ignore_errors() -> ContextManager[None]:
    """
    Use ``with ignore_errors(): <code>`` to ignore all errors in a bit of code (e.g. when making sure some file is
    closed in a `finally` block)
    """
    try:
        yield
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except:
        pass
