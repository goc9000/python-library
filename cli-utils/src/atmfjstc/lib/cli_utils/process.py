"""
Utilities for working with external processes.
"""

import shutil
import subprocess
import re
import textwrap

from os import PathLike
from typing import Any, AnyStr, Optional, Mapping, IO, Union, Type

from atmfjstc.lib.text_utils import ucfirst, add_prompt, iter_wrap_items, iter_limit_text


def command_exists(command: str) -> bool:
    """
    Checks whether some external utility is installed and accessible to this script.

    Args:
        command: The name of the binary/command to look for. It must be a single name; arguments and shell command lines
            are not accepted.

    Returns:
        True if the command exists and is accessible (as per `which`).
    """
    return shutil.which(command) is not None


Handle = Union[IO, int, Type[subprocess.PIPE], None]
PathType = Union[PathLike, bytes, str]


def run_external(
    command: str, *args: Any,
    stdin: Handle = None, input: AnyStr = None, stdout: Handle = None, stderr: Handle = None,
    capture_output: bool = True, text: bool = False, encoding: Optional[str] = None, errors: Optional[str] = None,
    shell: bool = False, cwd: Optional[PathType] = None, env: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None, check_retcode: bool = True, check_stderr: bool = True
) -> subprocess.CompletedProcess:
    """
    Calls an external utility in a manner similar to `subprocess.run()`, with some extra niceties:

    - The exceptions thrown by `subprocess.run()` (`OSError` for non-accessible executables, vs `SubprocessError` for
      bad returncodes and timeouts) are replaced by the overarching class `RunExternalError` and its subclasses. These
      exceptions also present much richer info by default.
    - `capture_output` defaults to True
    - `check` is now named `check_retcode` and defaults to True
    - An option `check_stderr` that causes an error to be thrown if the called process writes anything to stderr
      (defaults to True). The stderr output is automatically decoded regardless of the `text` setting and a limited
      amount of it is included in the exception.

    Args:
        command: The command to run. Must be either a binary name, or, if `shell` is True, can be a complete command
           line.
        *args: The arguments to the command. They will be automatically coerced to strings.
        stdin: See `subprocess.run`.
        input: See `subprocess.run`.
        stdout: See `subprocess.run`.
        stderr: See `subprocess.run`.
        capture_output: See `subprocess.run`.
        text: See `subprocess.run`.
        encoding: See `subprocess.run`.
        errors: See `subprocess.run`.
        shell: See `subprocess.run`.
        cwd: See `subprocess.run`.
        env: See `subprocess.run`.
        timeout: The number of seconds to wait for the command to complete before timing out.
        check_retcode: If True, a non-zero return code will be interpreted as an error.
        check_stderr: If True, anything being written to stderr will be interpreted as an error (capturing stderr must
            be enabled for this)

    Returns:
        A `CompletedProcess` object containing the captured program output, return code, etc. (see the builtin
        `subprocess.CompletedProcess` class for details)

    Raises:
        RunExternalLaunchError: If the command could not be launched
        RunExternalCalledProcessError: If the command reported an error (either through the returncode or stderr)
        RunExternalTimeoutError: If the command timed out
        RunExternalOtherError: For any other unexpected error
    """

    try:
        result = subprocess.run(
            (command, *(str(arg) for arg in args)),
            stdin=stdin, input=input, stdout=stdout, stderr=stderr, capture_output=capture_output, shell=shell,
            cwd=cwd, timeout=timeout, encoding=encoding, errors=errors, text=text, env=env,
        )
    except subprocess.SubprocessError as e:
        raise RunExternalError.from_std_error(e)
    except OSError as e:
        raise RunExternalError.from_std_error(e, command, args)

    check_external_cmd_result(result, check_retcode=check_retcode, check_stderr=check_stderr)

    return result


def check_external_cmd_result(
    result: subprocess.CompletedProcess, check_retcode: bool = True, check_stderr: bool = True
) -> subprocess.CompletedProcess:
    """
    Analyzes a `CompletedProcess` result and throws an error if the return code or stderr indicate the program failed.

    Basically this does the check at the end of `run_external` in case you didn't check the return code or stderr
    immediately (e.g. because you had to do some processing on the result first).

    Args:
        result: A `CompletedProcess` object containing a program result
        check_retcode: If True, a non-zero return code will be interpreted as an error.
        check_stderr: If True, a non-empty stderr capture will be interpreted as an error

    Returns:
        The same `CompletedProcess` result.

    Raises:
        RunExternalCalledProcessError: If the command reported an error (either through the returncode or stderr)
    """

    if (check_retcode and (result.returncode != 0)) or (check_stderr and len(result.stderr or '') > 0):
        raise RunExternalCalledProcessError(result)

    return result


class RunExternalError(Exception):
    command = None
    args = None
    return_code = None
    stdout = None
    stderr = None

    def __init__(
        self, message_base, command, args, retcode, stdout, stderr,
        quoted_error=None, quoted_output=None, show_retcode=True
    ):
        self.command = command
        self.args = args or ()
        self.return_code = retcode
        self.stdout = stdout
        self.stderr = stderr

        super().__init__(_render_external_error_message(
            message_base, command, args, retcode,
            quoted_error=quoted_error, quoted_output=quoted_output, show_retcode=show_retcode
        ))

    @staticmethod
    def from_std_error(error, command=None, args=None):
        if isinstance(error, OSError):
            return RunExternalLaunchError(error, command, args)
        elif isinstance(error, subprocess.CalledProcessError):
            return RunExternalCalledProcessError(error)
        elif isinstance(error, subprocess.TimeoutExpired):
            return RunExternalTimeoutError(error)
        else:
            return RunExternalOtherError(error, command, args)


class RunExternalLaunchError(RunExternalError):
    error = None

    def __init__(self, underlying_error, command, args):
        self.error = underlying_error

        super().__init__(
            "Could not launch {}",
            command, args or (), None, None, None,
            quoted_error=underlying_error
        )


class RunExternalCalledProcessError(RunExternalError):
    def __init__(self, called_proc_result_or_error):
        cpr = called_proc_result_or_error  # Shortcut
        if isinstance(cpr, subprocess.CompletedProcess):
            raw_command = cpr.args
        elif isinstance(cpr, subprocess.CalledProcessError):
            raw_command = cpr.cmd
        else:
            raise TypeError("Must be called on either CompletedProcess or CalledProcessError")

        command, args = _split_cmd_args(raw_command)

        if (cpr.stderr is not None) and (len(cpr.stderr) > 0):
            head = "{} reported an error"
            quoted_output = cpr.stderr
            show_retcode = True
        else:
            head = f"{{}} reported a failure return code ({cpr.returncode})"
            quoted_output = None
            show_retcode = False

        super().__init__(
            head,
            command, args, cpr.returncode, cpr.stdout, cpr.stderr,
            quoted_output=quoted_output, show_retcode=show_retcode
        )


class RunExternalTimeoutError(RunExternalError):
    def __init__(self, from_error):
        assert isinstance(from_error, subprocess.TimeoutExpired)

        command, args = _split_cmd_args(from_error.cmd)

        super().__init__(
            f"{{}} timed out at {from_error.timeout} seconds",
            command, args, None, from_error.stdout, from_error.stderr
        )


class RunExternalOtherError(RunExternalError):
    error = None

    def __init__(self, from_error, command, args):
        self.error = from_error

        super().__init__(
            "Unexpected error while launching {}",
            command, args or (), None, None, None,
            quoted_error=from_error
        )


def _split_cmd_args(raw_command):
    if isinstance(raw_command, (str, bytes)):
        return raw_command, ()

    return raw_command[0], tuple(raw_command[1:])


def _render_external_error_message(
    message_base, command, args, retcode, quoted_error=None, quoted_output=None, show_retcode=True, max_width=120
):
    if command is not None:
        command_name = f"command '{command}'" if _looks_like_shell_command(command) else f"'{command}'"
    else:
        command_name = 'command'

    message_parts = [
        ucfirst(message_base.format(command_name)) +
        (':' if (quoted_error or quoted_output) is not None else '')
    ]

    if quoted_error is not None:
        err_str = str(quoted_error)
        if ('\n' not in err_str) and (len(message_parts[0]) + len(err_str) + 1 < max_width):
            message_parts[0] += ' ' + err_str
        else:
            message_parts.append(textwrap.indent(err_str, '  '))

    if quoted_output is not None:
        emitted = False
        for line in iter_limit_text(
            _parse_output(quoted_output), max_lines=10, max_width=max_width-2, long_lines='wrap'
        ):
            message_parts.append('> ' + line)
            emitted = True

        if not emitted:
            message_parts.append('(no stderr output)')

    if show_retcode and (retcode is not None):
        message_parts.append(f"Return code: {retcode}")

    if len(args or ()) > 0:
        prompt = "Args: "

        message_parts.append(add_prompt(
            prompt,
            '\n'.join(iter_wrap_items([_quote_arg(arg) for arg in args], max_width - len(prompt)))
        ))

    return '\n'.join(part for part in message_parts)


def _quote_arg(arg):
    return repr(arg) if re.search(r'[ \'"]', arg) else arg


def _looks_like_shell_command(command):
    return re.match(r'^[.0-9a-z_-]*$', command, re.I) is None


def _parse_output(raw_output):
    if raw_output is None:
        return []
    if isinstance(raw_output, bytes):
        raw_output = raw_output.decode('utf-8', errors='replace')

    return raw_output.splitlines(False)
