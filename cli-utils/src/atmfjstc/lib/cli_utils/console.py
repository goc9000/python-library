"""
Console abstraction useful for command-line utilities that need to interact with the user via the terminal.

It provides functions for showing messages of various types (info, warnings, errors) in appropriate colors (where
available) and on the appropriate stream (stdout vs stderr), as well as requesting information (e.g. passwords) from
the user. Interactivity can easily be suspended, e.g. if the caller is used to feed a pipe to another program, via a
simple call, without any further modifications being required in the caller code.

The abstraction is provided as an object of type ``Console``, a singleton(-ish) instance of which is available through
the ``console`` property of this module. Thus one can use::

    from [...].console import console

    console.print_warning("test")

Notes:

- All communication with the user should be done using this abstraction. Don't use regular ``print()`` functions beside
  it (unless they are specifically directed to a file or some other stream).
- This abstraction is specifically intended for communication with a *human user* via *a terminal*, not for
  noninteractive communication between scripts. Use regular ``print()`` and ``.read()`` functions for that.
- The module is not specifically designed to be thread-safe, but nothing extremely disastrous should occur if multiple
  threads use the console (other than the interleaving of messages or parts thereof)
"""

import sys
import shutil
import subprocess

from getpass import getpass
from termcolor import cprint


class Console:
    """
    An abstraction for communicating with the user via the terminal.

    Don't create your own instances of this.
    """

    _interactive = None
    _stdout_enabled = None

    def __init__(self, enable_stdout=True, interactive=True):
        self._stdout_enabled = enable_stdout
        self._interactive = interactive

    def print_info(self, message_format, *args, **kwargs):
        """
        Print an informational message.

        An informational message is basically any message that does not fit into the other types.
        """
        self.print_message('info', message_format, *args, **kwargs)

    def print_prompt(self, message_format, *args, **kwargs):
        """
        Print a prompt message.

        This is any message that signals to the user that input is required (but is too long to place as the actual
        prompt to the left of the cursor).

        Example (the first line is the prompt message, the second is the actual prompt)::

          Archive entry 'a/b/c/d' is encrypted. Input the password, or leave blank to skip.
          Password: _
        """
        self.print_message('prompt', message_format, *args, **kwargs)

    def print_progress(self, message_format, *args, **kwargs):
        """
        Print a progress message.

        This is a message that shows the progress of an operation, either as a percentage, progress bar, etc., or even
        just as a phase indicator, e.g. "Loading data..."
        """
        self.print_message('progress', message_format, *args, **kwargs)

    def print_success(self, message_format, *args, **kwargs):
        """
        Print a success message.

        This is useful for signaling the end of a long operation. The message will be highlighted if the terminal
        supports colors.
        """
        self.print_message('success', message_format, *args, **kwargs)

    def print_warning(self, message_format, *args, **kwargs):
        """
        Print a warning message.

        The message will be highlighted in yellow and normally sent to stderr.
        """
        self.print_message('warning', message_format, *args, **kwargs)

    def print_error(self, message_format, *args, **kwargs):
        """
        Print an error message.

        The message will be highlighted in red and normally sent to stderr.
        """
        self.print_message('error', message_format, *args, **kwargs)

    def input_password(self, prompt):
        """
        Asks for a password from the user. An error is thrown if the console is not in interactive mode.

        The ``getpass`` module will be used so that the password can be entered in a secure way.
        """
        if not self._interactive:
            raise AssertionError("Tried to ask for a password but session is not interactive")

        return getpass(prompt)

    def notify_desktop(self, text, title=None):
        """
        Attempts to show a desktop notification. A terminal application that has been running in the background can use
        this to signal to the user the end of a long running operation (or some other update).

        This function runs on a best-effort basis and should not be relied upon for anything critical. On Linux, it
        makes use of the ``notify-send`` external program. On OS X, it uses ``terminal-notifier``, which must be
        installed using ``brew`` or the like.

        Returns True if displaying the notification was (most likely) successful, False if it definitely was not.
        """

        if shutil.which('notify-send'):  # For Linux
            return subprocess.run(
                ['notify-send'] + ([title] if title is not None else []) + [text]
            ).returncode == 0
        if shutil.which('terminal-notifier'):  # For OS X
            return subprocess.run(
                ['terminal-notifier', '-message', text] + (['-title', title] if title is not None else [])
            ).returncode == 0

        return False

    def is_interactive(self):
        """
        True if the console is in interactive mode (i.e. input can be asked from the user)
        """
        return self._interactive

    def disable_stdout(self):
        """
        Disables messages that would normally go to stdout (i.e. anything except warnings and errors).

        This is useful when a program normally outputs to a file but can also be instructed to write directly to
        stdout. In that case, we don't want progress messages to be intermixed with the program's proper output.
        """
        self._stdout_enabled = False
        return self

    def enable_stdout(self):
        """
        Re-enables messages to stdout (the normal state of the console)
        """
        self._stdout_enabled = True
        return self

    def disable_interactive(self):
        """
        Disables interactivity (i.e. signals that the program cannot stop to ask the user for input).

        Usually we need this when the caller is a script reading or writing to a pipe. A program that would normally
        ask for passwords, for instance, will be forced to use defaults or skip/fail the password-requiring operation.
        """
        self._interactive = False
        return self

    def enable_interactive(self):
        """
        Re-enables interactivity (the normal state of the console)
        """
        self._interactive = True
        return self

    def pipe_mode(self):
        """
        Enables "pipe mode", i.e. disables stdout and interactivity.

        Perfect for non-interactive scripts that just process data from one program and pipe it to another.
        """
        self.disable_stdout()
        self.disable_interactive()

    def print_message(self, kind, message_format, *args, **kwargs):
        """
        Prints a message of a programmatically specified type.

        :param kind: Can be 'info', 'prompt', 'progress', 'success', 'warning', 'error' with the meanings as described
                     by the respective ``print_*`` methods.
        """
        text = self._format_message(message_format, *args, **kwargs)

        props = _PROPS_BY_MSG_TYPE.get(kind)
        if props is None:
            props = _PROPS_BY_MSG_TYPE['default']

        channel_name = props.get('channel', 'stdout')
        if channel_name == 'stdout' and not self._stdout_enabled:
            return

        channel = sys.stderr if channel_name == 'stderr' else sys.stdout

        _print_maybe_with_color(text, props.get('color'), props.get('attrs'), channel)

    def _format_message(self, message_format, *args, **kwargs):
        # Trick to prevent errors when we don't actually want any formatting done
        if len(args) == 0 and len(kwargs) == 0:
            return message_format

        return message_format.format(*args, **kwargs)


def _print_maybe_with_color(text, color, attrs, channel):
    if (color is None) and (len(attrs or []) == 0):
        print(text, file=channel)
    else:
        cprint(text, color or 'white', attrs=attrs, file=channel)


_PROPS_BY_MSG_TYPE = {
    'default': dict(),
    'info': dict(),
    'prompt': dict(),
    'progress': dict(),
    'success': dict(color='green', attrs=['bold']),
    'warning': dict(color='yellow', attrs=['bold'], channel='stderr'),
    'error': dict(color='red', attrs=['bold'], channel='stderr'),
}


# Singleton
console = Console()
"""The currently active console abstraction."""
