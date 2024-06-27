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

import atexit
import os

from abc import ABCMeta, abstractmethod
from typing import Optional, Literal, IO
from pathlib import Path, PurePath

from atmfjstc.lib.file_utils import PathType
from atmfjstc.lib.error_utils import ignore_errors


def open_safe_output_file(
    path: PathType, text: bool = False, overwrite: Literal['deny', 'safe', 'unsafe'] = 'deny',
    success: Literal['nonempty', 'commit'] = 'nonempty', create_parent_dirs: bool = False,
    create_parent_mode: int = 0o755, encoding: Optional[str] = 'utf-8', errors: Optional[str] = None,
    newline: Optional[str] = None, buffering: int = -1
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
        success: If 'nonempty' (the default), the output file will be preserved if any content was written to it. For
            'commit', the file will be preserved only if `commit()` was explicitly called.
        create_parent_dirs: If True, parent directories for the output file will be created if missing. By default,
            missing parents will generate an error.
        create_parent_mode: The mode with which parent directories will be created, if `create_parent_dirs` is True
        encoding: See the built-in `open` function.
        errors: See the built-in `open` function.
        newline: See the built-in `open` function.
        buffering: See the built-in `open` function.

    Returns:
        A `SafeOutputFile` object that contains methods and properties for accessing the output file stream and deciding
        its fate (reject or commit changes) etc.

    Raises:
        SafeOutputFileError: For any failures in setting up the file (e.g. already exists, I/O error etc.)
        OutputFileParentDirAbsentError: If the parent directory of the output file does not exist
        OutputFileCreateParentDirError: If a parent directory of output file could not be created
        OutputFileBlockedByNonFileError: If a non-file (e.g. directory) entry by that name already exists
        OutputFileAlreadyExistsError: If the output file already exists and we are in 'deny' overwrite mode
        OutputFileBackupAlreadyExistsError: If we are operating in 'safe' overwrite mode and a backup already exists
            (left over from a crashed run?)
        OutputFileBackupMoveError: If we are operating in 'safe' overwrite mode and the previous version of the output
            cannot be backed up (permissions issue?)
        OutputFilePermissionsError: If opening the file failed due to inadequate permissions
        OutputFileOpenError: If opening the file failed due to any other reason
        ValueError: If any arguments to this function are invalid
    """

    if overwrite not in ['deny', 'safe', 'unsafe']:
        raise ValueError(f"overwrite= argument must be either 'deny', 'safe' or 'unsafe' (got: {overwrite!r})")

    path = PurePath(path)
    active_path = Path(path)
    backup_path = None

    if not active_path.parent.is_dir():
        if not create_parent_dirs:
            raise OutputFileParentDirAbsentError(path)

        # Path.mkdir(parents=True) ignores mode, so we resort to this
        _mk_parents_rec(active_path.parent, create_parent_mode, path)

    if _path_exists(active_path):
        if not active_path.is_file():
            raise OutputFileBlockedByNonFileError(path)
        if overwrite == 'deny':
            raise OutputFileAlreadyExistsError(path)
        elif overwrite == 'safe':
            backup_path = active_path.with_name(path.name + '.backup')
            if _path_exists(backup_path):
                raise OutputFileBackupAlreadyExistsError(path, PurePath(backup_path))

            try:
                active_path.rename(backup_path)
            except Exception as e:
                raise OutputFileBackupMoveError(path) from e

    mode = ('x' if (overwrite == 'deny') else 'w')

    cancel_backup = True
    try:
        if text:
            handle = open(path, mode + 't', encoding=encoding, errors=errors, newline=newline, buffering=buffering)
        else:
            handle = open(path, mode + 'b', buffering=buffering)

        cancel_backup = False
    except PermissionError as e:
        raise OutputFilePermissionsError(path) from e
    except Exception as e:
        raise OutputFileOpenError(path) from e
    finally:
        if cancel_backup and (backup_path is not None):
            backup_path.rename(active_path)

    record = _SafeOutputFile(handle, success, active_path, backup_path)

    atexit.register(record.finish)

    return record


def _path_exists(path: Path) -> bool:
    # Unlike path.exists(), this also handles broken symlinks (only on Python >=3.10 can we use follow_symlinks=False)
    try:
        _ = path.lstat()
    except FileNotFoundError:
        return False

    return True


def _mk_parents_rec(parent_path: Path, mode: int, outfile_path: PurePath):
    if not parent_path.parent.exists():
        _mk_parents_rec(parent_path.parent, mode, outfile_path)

    try:
        parent_path.mkdir(mode=mode)
        return
    except Exception as e:
        raise OutputFileCreateParentDirError(outfile_path, PurePath(parent_path)) from e


class SafeOutputFile(metaclass=ABCMeta):
    """
    An interface that represents an open output file.
    """

    @property
    @abstractmethod
    def handle(self) -> IO:
        """
        The file object (as returned by e.g. `open()`) that data can be written to
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def path(self) -> PurePath:
        """
        The path to the output file.
        """
        raise NotImplementedError

    @abstractmethod
    def commit(self, finish_now: bool = True):
        """
        Signal that the output file should be preserved, the output generation having been successful.

        The `finish()` method will also be called right away by default. If this is undesirable (e.g. the file system
        should not be accessed at the time), specify `finish_now=False`.
        """
        raise NotImplementedError

    @abstractmethod
    def abandon(self, finish_now: bool = True):
        """
        Signal that the output file should be abandoned (even if data was written to it).

        The `finish()` method will also be called right away by default. If this is undesirable (e.g. the file system
        should not be accessed at the time), specify `finish_now=False`.
        """
        raise NotImplementedError

    @abstractmethod
    def finish(self):
        """
        Resolves the fate of the output file by preserving or deleting it as appropriate.

        Once this function has been called once, calling it again has no effect.
        """
        raise NotImplementedError


class _SafeOutputFile(SafeOutputFile):
    _handle: IO
    _finished: bool
    _commit: bool
    _abandon: bool
    _success: Literal['nonempty', 'commit']
    _path: Path
    _backup_path: Optional[Path]

    def __init__(self, handle: IO, success: Literal['nonempty', 'commit'], path: Path, backup_path: Optional[Path]):
        self._handle = handle
        self._finished = False
        self._commit = False
        self._abandon = False
        self._success = success
        self._path = path
        self._backup_path = backup_path

    @property
    def handle(self) -> IO:
        return self._handle

    @property
    def path(self) -> PurePath:
        return PurePath(self._path)

    def commit(self, finish_now: bool = True):
        self._commit = True
        if finish_now:
            self.finish()

    def abandon(self, finish_now: bool = True):
        self._abandon = True
        if finish_now:
            self.finish()

    def finish(self):
        if self._finished:
            return

        self._finished = True

        if self._abandon:
            keep = False
        elif self._commit:
            keep = True
        elif self._success == 'nonempty' and self._is_nonempty():
            keep = True
        else:
            keep = False

        if keep:
            self._keep()
        else:
            self._discard()

    def _is_nonempty(self) -> bool:
        if not self._handle.closed:
            self._handle.seek(0, os.SEEK_END)
            return self._handle.tell() > 0

        return self._path.stat().st_size > 0

    def _keep(self):
        if self._backup_path is not None:
            with ignore_errors():
                self._backup_path.unlink()

    def _discard(self):
        # Ensure the file is closed (on POSIX it's OK to delete a file while it's being accessed, but not so sure on
        # Windows or other systems)
        if not self._handle.closed:
            with ignore_errors():
                self._handle.close()

        with ignore_errors():
            self._path.unlink()

        if self._backup_path is not None:
            with ignore_errors():
                self._backup_path.rename(self._path)


class SafeOutputFileError(Exception):
    path: PurePath

    def __init__(self, path: PurePath, message: str):
        self.path = path

        super().__init__(message)


class OutputFileParentDirAbsentError(SafeOutputFileError):
    def __init__(self, path: PurePath, message: Optional[str] = None):
        super().__init__(
            path,
            message or f"Output file '{path}' cannot be created because its parent directory does not exist"
        )


class OutputFileCreateParentDirError(SafeOutputFileError):
    parent_path: PurePath

    def __init__(self, path: PurePath, parent_path: PurePath, message: Optional[str] = None):
        self.parent_path = parent_path

        super().__init__(
            path, message or f"Can't create parent directory '{parent_path}' needed for output file '{path}'"
        )


class OutputFileBlockedByNonFileError(SafeOutputFileError):
    def __init__(self, path: PurePath, message: Optional[str] = None):
        super().__init__(
            path,
            message or f"Output file '{path}' cannot be created because a non-file entry by that name already exists"
        )


class OutputFileAlreadyExistsError(SafeOutputFileError):
    def __init__(self, path: PurePath, message: Optional[str] = None):
        super().__init__(path, message or f"Output file '{path}' already exists and overwrite is not allowed")


class OutputFileBackupAlreadyExistsError(SafeOutputFileError):
    backup_path: PurePath

    def __init__(self, path: PurePath, backup_path: PurePath, message: Optional[str] = None):
        self.backup_path = backup_path

        super().__init__(
            path, message or f"Can't back up previous version of output file as the path '{backup_path}' already exists"
        )


class OutputFileBackupMoveError(SafeOutputFileError):
    def __init__(self, path: PurePath, message: Optional[str] = None):
        super().__init__(
            path,
            message or f"Can't create output file '{path}' because its previous cannot be moved out of the way"
        )


class OutputFilePermissionsError(SafeOutputFileError):
    def __init__(self, path: PurePath, message: Optional[str] = None):
        super().__init__(path, message or f"No permissions to open output file '{path}'")


class OutputFileOpenError(SafeOutputFileError):
    def __init__(self, path: PurePath, message: Optional[str] = None):
        super().__init__(path, message or f"Output file '{path}' could not be opened")
