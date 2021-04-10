"""
A simple harness for daemons running on OS X (via `launchd`).

It takes care of a few issues, such as setting up logging, handling fatals and routing termination signals.

By default logging is done to stderr, so the plist should contain a `StandardErrorPath` key redirecting it to some log
file.
"""

import logging
import sys
import signal

from argparse import ArgumentParser, Namespace
from abc import ABCMeta, abstractmethod
from typing import Text, NoReturn, Union, Optional

from atmfjstc.lib.cli_utils.errors import fail, DescriptiveError


class OSXDaemon(metaclass=ABCMeta):
    """
    A harness for daemons designed to be run via `launchd`.
    """

    def argument_parser_params(self) -> dict:
        """
        Override this if desired, to configure the ArgumentParser for the daemon.

        Returns:
            A dict of parameters to pass to the ArgumentParser object
        """
        return dict()

    def setup_arguments(self, mut_parser: ArgumentParser):
        """
        Override this if desired, to configure command-line arguments for the daemon.

        Args:
            mut_parser: The daemon's ArgumentParser, ready to accept parameter definitions
        """
        pass

    def setup_logging(self, raw_args: Optional[Namespace]):
        """
        Override this if desired, to configure logging for the daemon.

        Args:
            raw_args: A Namespace object containing the parsed command-line arguments. Note that this may be None, if
                      an error occurred during command-line parsing. Logging MUST still be configured in this case,
                      using some sort of default settings.
        """
        logging.basicConfig(level='INFO', style='{', format='[{asctime}] {levelname}: {message}')

    def logger(self) -> logging.Logger:
        """
        Override this if desired, to change the logger used by the daemon harness.

        Returns:
            The Logger object
        """
        return logging.getLogger()

    @abstractmethod
    def run(self, raw_args: Namespace):
        """
        Override this with the main code of the daemon.

        Note that `launchd` expects the code to implement a 'run in foreground' model. Do not apply typical UNIX daemon
        tricks such as forking etc.

        The code should run indefinitely (or until a termination is requested). Once this method returns, the daemon
        will exit. To report errors or any other output, use the `logging` package. To report fatal errors, use `fail`
        or throw some other Exception.

        Args:
            raw_args: The arguments, as parsed by the ArgumentParser
        """
        raise NotImplementedError

    def on_terminate_requested(self):
        """
        Override this if desired, with the code that is to be executed when the daemon is asked to terminate.

        By default this raises a SystemException, but more advanced daemons may want to instead put an element in a
        queue, manage threads etc.
        """
        self.logger().info("Termination requested, shutting down...")
        sys.exit(0)

    def go(self):
        """
        Starts the harness. Call this in `__main__` (and do nothing else).
        """

        _catch_term = lambda _sig_num, _frame: self.on_terminate_requested()

        signal.signal(signal.SIGTERM, _catch_term)
        signal.signal(signal.SIGHUP, _catch_term)

        raw_args = self._parse_raw_args()
        self.setup_logging(raw_args if isinstance(raw_args, Namespace) else None)

        try:
            if isinstance(raw_args, Exception):
                raise raw_args

            self.run(raw_args)
        except KeyboardInterrupt:
            self.logger().info("Shut down by user")
            sys.exit(0)
        except DescriptiveError as e:
            self.logger().fatal(str(e))
            sys.exit(-1)
        except Exception as e:
            self.logger().fatal("Unexpected exception", exc_info=e)
            sys.exit(-1)

    def _parse_raw_args(self) -> Union[Namespace, Exception]:
        """
        Parse the args. Three situations are possible:

        - The user specified `--help` on the command line (e.g. when debugging) -> the program stops here
        - The parameters were parsed OK -> returns them as a Namespace object
        - There was an error -> returns the exception and does not exit yet (because we might want to report it only
                                after logging has been initialized)
        """
        try:
            arg_parser = _ArgumentParser(**self.argument_parser_params())

            self.setup_arguments(arg_parser)

            return arg_parser.parse_args()
        except Exception as e:
            return e


class _ArgumentParser(ArgumentParser):
    def error(self, message: Text) -> NoReturn:
        # We need this because exit_on_error= doesn't work, lol
        fail(message)
