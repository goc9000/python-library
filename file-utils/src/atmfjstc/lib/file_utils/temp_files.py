"""
Utilities for working with temporary files.
"""

import os

from typing import IO, Optional, AnyStr, Iterator
from tempfile import TemporaryDirectory, NamedTemporaryFile
from shutil import copyfileobj
from contextlib import contextmanager, suppress

from atmfjstc.lib.file_utils import PathType
from atmfjstc.lib.file_utils.fileobj import get_fileobj_size


@contextmanager
def named_temp_file(
    suffix: Optional[AnyStr] = None, prefix: Optional[AnyStr] = None, dir: Optional[PathType] = None,
    mode: str = 'w+b', buffering: int = -1,
    encoding: Optional[str] = None, newline: Optional[str] = None, errors: Optional[str] = None
) -> Iterator[IO]:
    """
    Similar to `tempfile.NamedTemporaryFile` but allows for the file to be closed without being deleted. The file will
    only be deleted when the context is closed.

    This is crucial if we e.g. want to pass the file to another utility, since on Windows, other programs will not be
    able to open the file while we are still keeping it open for writing.

    The standard `NamedTemporaryFile` can only be configured in this way starting with Python 3.12 ; this solution
    works with earlier Python versions.

    Args:
        suffix: The desired suffix for the temporary file.
        prefix: The desired prefix for the temporary file.
        dir: The path of the parent directory for the temporary file.
        mode: See the `open` function.
        buffering: See the `open` function.
        encoding: See the `open` function.
        newline: See the `open` function.
        errors: See the `open` function.

    Returns:
        The context manager will return the temporary file as an open file object.
    """

    filename = None

    try:
        with NamedTemporaryFile(
            mode=mode, buffering=buffering, encoding=encoding, newline=newline,
            suffix=suffix, prefix=prefix, dir=dir,
            delete=False, errors=errors,
        ) as tmp_file:
            filename = tmp_file.name

            try:
                yield tmp_file
            finally:
                with suppress(OSError):
                    tmp_file.close()
    finally:
        if filename is not None:
            with suppress(OSError, PermissionError):
                os.remove(filename)


@contextmanager
def specifically_named_temp_file(
    name: AnyStr, suffix: Optional[AnyStr] = None, prefix: Optional[AnyStr] = None, dir: Optional[PathType] = None,
    mode: str = 'w+b', buffering: int = -1,
    encoding: Optional[str] = None, newline: Optional[str] = None, errors: Optional[str] = None
) -> Iterator[IO]:
    """
    Similar to `named_temp_file` but creates a temporary file with a specific name. This is particularly useful for
    calling external binaries that care about the exact name of the file they operate upon (e.g. archivers).

    The `suffix`, `prefix` and `dir` parameters apply to a temporary directory created to contain the file.

    As with `named_temp_file`, the file and its containing directory are deleted when the context is closed.

    Args:
        name: The name with which the temporary file will be created.
        suffix: The desired suffix for the temporary directory holding the temporary file.
        prefix: The desired prefix for the temporary directory holding the temporary file.
        dir: The path of the parent directory for the temporary directory holding the temporary file.
        mode: See the `open` function.
        buffering: See the `open` function.
        encoding: See the `open` function.
        newline: See the `open` function.
        errors: See the `open` function.

    Returns:
        The context manager will return the temporary file as an open file object.
    """

    assert name == os.path.basename(name), "Must provide a basename, not a path"

    with TemporaryDirectory(suffix=suffix, prefix=prefix, dir=dir) as temp_dir_name:
        tmp_file = open(
            os.path.join(temp_dir_name, name),
            mode=mode, buffering=buffering, encoding=encoding, newline=newline, errors=errors
        )

        try:
            yield tmp_file
        finally:
            with suppress(OSError):
                tmp_file.close()


class FileTooBigError(ValueError):
    actual_size: int
    allowed_size: int

    def __init__(self, actual_size: int, allowed_size: int):
        super().__init__(
            f"Cannot write temporary file, size ({round(actual_size / 1000000)} MB) exceeds limit "
            f"({round(allowed_size / 1000000)} MB)"
        )

        self.actual_size = actual_size
        self.allowed_size = allowed_size


@contextmanager
def temp_drop_file_obj_to_disk(
    fileobj: IO, safety_limit_mb: Optional[int] = None, rewind: bool = False, specific_name: Optional[AnyStr] = None
) -> Iterator[AnyStr]:
    """
    Temporarily copies the contents of an arbitrary file object to disk, for access by an external utility.

    It may sometimes happen that we have some data accessible via a file object that does not directly correspond to an
    on-disk file (e.g. in memory, or generated by some abstraction such as a decompressor), and we need to run some
    external utility on it (e.g. an archiver). Normally we could try piping it to the utility, but if the utility has
    no stdin support, we need to write the data to a temporary file. This context manager does all the necessary copying
    and returns the visible file name of the saved data, which will exist for as long as the context is open.

    Note that if the file object is seekable, the function will ensure that it is rewound to its original position
    whenever control leaves this function, so that other functions may use the data as well.

    Args:
        fileobj: A file object containing the data we need to save to disk
        safety_limit_mb: If provided, the function will check for the size of the file that would be written (the
            fileobj needs to be seekable for this) and throw a `FileTooBig` error if it exceeds the stated limit. The
            value is provided in megabytes.
        rewind: By default, this function does not automatically rewind the file object to 0 before copying - it will
            copy only the data from the current position of the file object to the end. Set this to True to have the
            function do this rewinding for you. Note that the file object will still regain its original position
            afterwards.
        specific_name: If provided, the data will be saved with the given filename (required for some utilities which
            take the filename into account).

    Returns:
        The context manager returns the path of the file to which the data was saved. The file will disappear with the
        closing of the context.

    Raises:
        FileTooBig: Thrown if the safety limit is enabled, and the size of the file that would be written exceeds the
            stated amount.
    """

    assert (safety_limit_mb is None) or fileobj.seekable(), "File obj must be seekable if safety_limit_mb is provided"
    assert (not rewind) or fileobj.seekable(), "File obj must be seekable if rewind=True"

    original_position = fileobj.tell() if fileobj.seekable() else None

    def _maybe_restore_position():
        if original_position is not None:
            try:
                fileobj.seek(original_position)
            except Exception:
                pass

    # Do size check
    if safety_limit_mb is not None:
        file_size = get_fileobj_size(fileobj, 'start' if rewind else 'current')
        if file_size > (safety_limit_mb * 1000000):
            raise FileTooBigError(file_size, safety_limit_mb * 1000000)

    try:
        if specific_name is not None:
            temp_file = specifically_named_temp_file(specific_name)
        else:
            temp_file = named_temp_file()

        with temp_file as f:
            if rewind:
                fileobj.seek(0)

            copyfileobj(fileobj, f)
            f.close()  # Close the file - very important on Windows!

            _maybe_restore_position()

            yield f.name
    finally:
        _maybe_restore_position()
