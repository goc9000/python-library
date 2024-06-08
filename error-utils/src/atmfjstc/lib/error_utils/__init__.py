"""
Utilities for working with exceptions and other failure states.
"""

import traceback

from typing import ContextManager
from textwrap import dedent, indent
from contextlib import contextmanager
from abc import abstractmethod, ABCMeta


__version__ = '1.3.2'


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


class WarningWithMessage(UserWarning):
    """
    Convenient base class for warnings that contain a message.

    The message programmed into the warning will show up when `str()` is called on the warning. This happens
    automatically for Exceptions but not for Warnings, hence the need for this class.
    """

    def __init__(self, message: str):
        super().__init__(message)

    def __str__(self) -> str:
        return self.args[0]


class WarningWithContext(WarningWithMessage, metaclass=ABCMeta):
    """
    Base class for warnings that contain context info.

    Warnings of this class contain context info (i.e. info on which specific entry, location etc. in some broader scope
    the warning pertains to) and methods to generate a `str()` representation either with or without the context info
    attached. By default, the str() representation will show the context info.
    """

    def __init__(self, message: str):
        super().__init__(message)

    def __str__(self) -> str:
        return self.str_with_context()

    @abstractmethod
    def str_with_context(self) -> str:
        raise NotImplementedError

    def str_without_context(self) -> str:
        return self.args[0]
