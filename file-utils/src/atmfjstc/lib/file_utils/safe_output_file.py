"""
Module for robustly opening an output file.

Rationale
---------

Suppose the following scenario. A program needs to perform some analysis and save its results to an output file (usually
chosen by the user). The most natural and intuitive structure for this program would be:

- Perform the analysis and store the results in memory
- Open the output file
- Write the results to the output file

The problem with this sequence is that opening the output file may fail for a variety of reasons: invalid filename,
another entry with the same name exists, insufficient permissions etc. If we discover this situation only *after* we
have performed the analysis, we are going to have a bad time if the operation happened to be destructive or very
expensive.

What if we open the output file *before* performing the analysis? This allows us to catch errors early on and solves
most of the problems mentioned above. However, now we need to handle the case when the program fails before being
able to write to the output file. The zero-sized output file needs to be deleted, so that the final state on disk is
the same as if the output file had been scheduled to be open only after the analysis.

A further complication ensues when we allow for the possibility of the output file overwriting another file at the
same location (usually a previous version of the output). Ideally we would want to preserve the old output if the
program fails to complete, and only replace it upon success. This requires backing up the old file and deleting the
backup if the new output file was written successfully, or restoring the backup if it was not.

Solution
--------

This module provides a `open_safe_output_file` function that transparently handles all of the above cases. It should
be called as early as possible in the program, and it automatically ensures that:

- A zero-length output file is created immediately, thus validating that we have permission for creating files and that
  the filename is valid

  - If overwrites are allowed, the previous version of the file will be moved out of the way

- The application will hold on to the file while the analysis is executing, preventing other applications from
  accidentally taking up that file entry
- If the application crashes or otherwise fails, then:

  - The zero-length or partially written output file will be deleted
  - The previous output file, if any, will be restored

- Otherwise, if the analysis/operation completes successfully, changes will be persisted. The file will remain on disk
  and any previous version will be deleted.

Caution: This module is not designed to be thread or multiprocess-safe.
"""

from abc import ABCMeta

from typing import Optional, Literal

from atmfjstc.lib.file_utils import PathType


def open_safe_output_file(
    path: PathType, text: bool = False, overwrite: Literal['deny', 'safe', 'unsafe'] = 'deny',
    encoding: Optional[str] = 'utf-8', errors: Optional[str] = None, newline: Optional[str] = None, buffering: int = -1
) -> 'SafeOutputFile':
    """
    Open an output file in the safe manner as described in the package documentation.

    Args:
        path: The path of the file to open.
        text: By default, the file is opened in binary mode. Set this to True to open it in text mode.
        overwrite: If 'deny' (the default), the function will simply fail if the output file already exists. If 'safe',
            existing output files will be treated in the safe manner described in the package documentation (i.e. moved
            out of the way and replaced only if the operation was successful). If 'unsafe', files will be overwritten
            blindly.
        encoding: See the built-in `open` function.
        errors: See the built-in `open` function.
        newline: See the built-in `open` function.
        buffering: See the built-in `open` function.

    Returns:
        A `SafeOutputFile` object that contains methods and properties for accessing the output file stream and deciding
        its fate (reject or commit changes) etc.

    Raises:
        SafeOutputFileError: For any failures in setting up the file (e.g. already exists, I/O error etc.)
    """
    raise NotImplementedError


class SafeOutputFileError(RuntimeError):
    pass


class SafeOutputFile(metaclass=ABCMeta):
    pass
