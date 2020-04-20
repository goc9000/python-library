"""
Utilities for working with exceptions and other failure states.
"""

import traceback

from textwrap import dedent, indent


def format_exception_head(exception: BaseException) -> str:
    """
    Formats the head of an exception (i.e. the class and message, without the traceback) as it would appear when printed
    by Python's exception handler.

    Args:
        exception: The exception to format

    Returns:
        A string, possibly multiline, with the exception head text. There is no newline at the end.
    """
    return ''.join(traceback.format_exception_only(exception.__class__, exception)).rstrip()


def format_exception_trace(exception: BaseException) -> str:
    """
    Formats the traceback part of an exception as it would appear when printed by Python's exception handler.

    Args:
        exception: The exception to format

    Returns:
        A string, usually multiline, with the traceback info. There is no newline at the end and no ``'Traceback:'``
        header. The text has a base indent of 0, so as to allow you to add your own.
    """
    return dedent(''.join(traceback.format_list(traceback.extract_tb(exception.__traceback__))).rstrip())


def full_format_exception(exception: BaseException, follow_cause: bool = True) -> str:
    """
    Formats an exception in a manner similar to how it would appear when printed by Python's exception handler.

    All info will be shown: the exception class, message, traceback, as well as any chained causes. Note that unlike
    the Python exception handler, this will show the exception and its causes in reverse chronological order.

    Args:
        exception: The exception to format
        follow_cause: Whether to show `__cause__` exceptions. True by default.

    Returns:
       A string containing the fully formatted exception info. It will not end in a newline.
    """

    parts = [format_exception_head(exception), '  Traceback:', indent(format_exception_trace(exception), '    ')]

    if follow_cause and exception.__cause__:
        parts.append('  Cause:')
        parts.append(indent(full_format_exception(exception.__cause__), '    '))

    return '\n'.join(parts)
