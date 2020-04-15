"""
Utilities for working with temporary files.
"""

import os

from tempfile import TemporaryDirectory, NamedTemporaryFile
from shutil import copyfileobj
from contextlib import contextmanager, suppress


@contextmanager
def specifically_named_temp_file(
    name, suffix=None, prefix=None, dir=None, mode='w+b', buffering=-1, encoding=None, newline=None, errors=None
):
    """
    Similar to `tempfile.NamedTemporaryFile` but creates a temporary file with a specific name.

    The `suffix`, `prefix` and `dir` parameters apply to a temporary directory created to contain the file. There is
    no `delete=` option - the file and its containing directory are always deleted when the context is closed.
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
    actual_size = None
    allowed_size = None

    def __init__(self, actual_size, allowed_size):
        super().__init__(
            f"Cannot write temporary file, size ({round(actual_size / 1000000)} MB) exceeds limit "
            f"({round(allowed_size / 1000000)} MB)"
        )

        self.actual_size = actual_size
        self.allowed_size = allowed_size


@contextmanager
def temp_drop_file_obj_to_disk(fileobj, safety_limit_mb=None, rewind=False, specific_name=None):
    """
    Temporarily copies the contents of an arbitrary file object to disk.

    It may sometimes happen that we have some data accessible via a file object that does not directly correspond to an
    on-disk file (e.g. in memory, or deep within several decompression abstractions on a disk file), and we need to
    run some external utility on it (e.g. a decompressor). Normally we could try piping it to the utility, but if the
    utility has no stdin support, we need to write the data to a temporary file. This context manager does all the
    necessary copying and returns the visible file name of the saved data, which will exist for as long as the context
    is open.

    If `specific_name` is provided, the data will be saved under that exact filename (required for some utilities which
    take the filename into account).

    If `safety_limit_mb` is provided, the function will check for the size of the file (the fileobj needs to be seekable
    for this) that would be written and throw a FileTooBig error if it exceeds the stated limit.

    Notes:

    - If the file object is seekable, the function will ensure that it is rewound to its original position whenever
      control leaves this function, so that other functions may use the data as well
    - By default, this function does not automatically rewind the file object to 0 before copying - it will copy only
      the data from the current position of the file object to the end. Set rewind=True to have the function do this
      rewinding for you. Note that the file object will still regain its original position afterwards.
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
        fileobj.seek(0, 2)
        file_size = fileobj.tell() - (0 if rewind else original_position)
        _maybe_restore_position()

        if file_size > (safety_limit_mb * 1000000):
            raise FileTooBigError(file_size, safety_limit_mb * 1000000)

    try:
        if specific_name is not None:
            named_temp_file = specifically_named_temp_file(specific_name)
        else:
            named_temp_file = NamedTemporaryFile()

        with named_temp_file as f:
            if rewind:
                fileobj.seek(0)

            copyfileobj(fileobj, f)
            f.flush()

            _maybe_restore_position()

            yield f.name
    finally:
        _maybe_restore_position()
