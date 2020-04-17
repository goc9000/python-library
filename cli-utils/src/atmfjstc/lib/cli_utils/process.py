"""
Utilities for working with external processes.
"""

import shutil


def command_exists(command):
    """
    Checks whether some external utility is installed and accessible to this script.
    """
    return shutil.which(command) is not None
