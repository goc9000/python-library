from dataclasses import dataclass
from collections.abc import Set
from typing import Optional, Callable
from enum import Enum, auto


class SourceType(Enum):
    DICT = auto()
    OBJ = auto()


class DestinationType(Enum):
    DICT = auto()
    OBJ = auto()


@dataclass(frozen=True)
class DestinationSpec:
    type: DestinationType
    by_ref: bool


@dataclass(frozen=True)
class FieldSpec:
    source: str  # Name of field to copy data from
    destination: str  # Name of field to copy data to
    required: bool = False
    skip_empty: bool = False
    filter: Optional[Callable[[any], bool]] = None
    if_different: Optional[str] = None  # Only copy if it is different to this other field (before conversion)
    convert: Optional[Callable[[any], any]] = None


@dataclass(frozen=True)
class ConversionSpec:
    source_type: SourceType
    destination: DestinationSpec
    fields: tuple[FieldSpec, ...]
    ignored_fields: Set[str]
    return_unparsed: bool
    none_means_missing: bool
