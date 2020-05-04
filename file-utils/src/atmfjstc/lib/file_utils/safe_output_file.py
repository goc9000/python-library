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
the same as if the output file had been scheduled to be open only after the analyiss.

A further complication ensues when we allow for the possibility of the output file overwriting another file at the
same location (usually a previous version of the output). Ideally we would want to preserve the old output if the
program fails to complete, and only replace it upon success. This requires backing up the old file and deleting the
backup if the new output file was written successfully, or restoring the backup if it was not.

Solution
--------

This module provides a `open_safe_output_file` function that transparently handles all of the above cases. It should
be called as early as possible in the program and it automatically ensures that:

- A zero-length output file is created immediately, thus validating that we have permission for creating files and that
  the filename is valid

  - If overwrites are allowed, the previous version of the file will be moved out of the way

- The application will hold on to the file while the analysis is executing, preventing other applications from
  accidentally taking up that file entry
- If the application crashes without having called `write` on the file, then:

  - The temporary zero-length output file will be deleted
  - The previous output file, if any, will be restored

- Otherwise, if `write` has been called, and the file is closed or the program exits, changes will be persisted. The
  file will remain on disk and any previous version will be deleted.

Caution: This module is not designed to be thread or multiprocess-safe.
"""

import atexit

from typing import IO, Optional, Any, AnyStr, Iterable
from pathlib import Path

from atmfjstc.lib.file_utils import PathType
from atmfjstc.lib.error_utils import ignore_errors


def open_safe_output_file(
    path: PathType, overwrite: bool = False, text: bool = False,
    encoding: Optional[str] = 'utf-8', errors: Optional[str] = None, newline: Optional[str] = None, buffering: int = -1
) -> 'SafeOutputFile':
    """
    Open an output file in the safe manner as described in the package documentation.

    Args:
        path: The path of the file to open.
        overwrite: By default, this function will refuse to overwrite an existing file of the same name. Set this to
            True to enable a 'safe overwrite' in which any existing file will be replaced, but only if the write
            completes successfully.
        text: By default, the file is opened in binary mode. Set this to True to open it in text mode.
        encoding: See the built-in `open` function.
        errors: See the built-in `open` function.
        newline: See the built-in `open` function.
        buffering: See the built-in `open` function.

    Returns:
        An open file object-like instance for the output file.

    Raises:
        SafeOutputFileError: For any failures in setting up the file (e.g. already exists, I/O error etc.)
    """
    success = False
    outfile = None

    try:
        path = Path(path)
        outfile = SafeOutputFile(path)
        atexit.register(outfile._cleanup)

        if path.exists():
            if not path.is_file():
                raise RuntimeError("There is already a non-file entry by that name")
            if not overwrite:
                raise RuntimeError("File already exists and overwrite is disabled")

            backup_path = path.with_name(path.name + '.backup')
            if backup_path.is_file():
                raise RuntimeError(f"Cannot back up existing file to path '{backup_path}' as it already exists")

            path.rename(backup_path)

            outfile._backup_path = backup_path

        mode = ('w' if overwrite else 'x')

        if text:
            outfile._handle = open(
                path, mode + 't', encoding=encoding, errors=errors, newline=newline, buffering=buffering
            )
        else:
            outfile._handle = open(path, mode + 'b', buffering=buffering)

        success = True

        return outfile
    except Exception as e:
        raise SafeOutputFileError(f"Could not open output file '{path}'") from e
    finally:
        if (not success) and (outfile is not None):
            outfile._cleanup()


class SafeOutputFileError(RuntimeError):
    pass


class SafeOutputFile(IO):
    """
    A file object-like instance representing an output file.

    Do not interfere with the underscore-preceded methods and fields.
    """

    _path: Path
    _backup_path: Optional[Path] = None
    _handle: Optional[IO] = None
    _persist: bool = False
    _did_cleanup: bool = False

    def __init__(self, path):
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def writelines(self, lines: Iterable[AnyStr]) -> None:
        if self._handle is None:
            raise ValueError("Output file not initialized")

        self._handle.writelines(lines)

        self._persist = True

    def write(self, data: AnyStr) -> int:
        if self._handle is None:
            raise ValueError("Output file not initialized")

        result = self._handle.write(data)

        self._persist = True

        return result

    def persist(self):
        self._persist = True

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()

        self._cleanup()

    # Allow access to all other methods of the underlying file object
    def __getattr__(self, name: str) -> Any:
        if self._handle is None:
            raise ValueError("Output file not initialized")

        return getattr(self._handle, name)

    def _cleanup(self):
        if self._did_cleanup:
            return

        self._did_cleanup = True

        # Ensure file is closed
        if self._handle is not None:
            with ignore_errors():
                if not self._handle.closed:
                    self._handle.close()

        if self._persist:
            if self._backup_path is not None:
                with ignore_errors():
                    self._backup_path.unlink()
        else:
            if self._handle is not None:
                with ignore_errors():
                    self._path.unlink()

            if self._backup_path is not None:
                with ignore_errors():
                    self._backup_path.rename(self._path)
