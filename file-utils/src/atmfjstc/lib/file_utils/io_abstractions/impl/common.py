from typing import Optional, TypeVar, Dict
from pathlib import Path

from .. import ResolvedBinaryDataInterfaceCommon


Self = TypeVar('Self', bound='ResolvedBinaryDataInterfaceCommon')


class ResolvedBinaryDataInterfaceBase(ResolvedBinaryDataInterfaceCommon):
    _filename_override: Optional[str] = None

    def __init__(self, filename_override: Optional[str] = None):
        self._filename_override = filename_override

    def christen(self: Self, name: str) -> Self:
        return self._derive(filename_override=name)

    @property
    def filename(self) -> Optional[str]:
        return self._filename_override or self._natural_filename

    @property
    def _natural_filename(self) -> Optional[str]:
        return None  # Default, override in children as necessary

    @property
    def location_on_filesystem(self) -> Optional[Path]:
        return None  # Default, override in children as necessary

    def _derive(self: Self, **overrides) -> Self:
        return self.__class__(**{**self._constructor_args(), **overrides})

    def _constructor_args(self) -> Dict:
        return dict(filename_override=self._filename_override)


class FilesystemBasedBinaryDataInterfaceBase(ResolvedBinaryDataInterfaceBase):
    _path: Path

    def __init__(self, path: Path, filename_override: Optional[str] = None):
        super().__init__(filename_override=filename_override)

        self._path = path

    @property
    def _natural_filename(self) -> Optional[str]:
        return self._path.name

    @property
    def location_on_filesystem(self) -> Optional[Path]:
        return self._path

    def _constructor_args(self) -> Dict:
        return dict(**super()._constructor_args(), path=self._path)
