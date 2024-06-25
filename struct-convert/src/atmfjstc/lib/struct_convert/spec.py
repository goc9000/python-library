from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum, auto


class SourceType(Enum):
    DICT = auto()
    OBJ = auto()


class DestinationType(Enum):
    DICT = auto()
    DICT_BY_REF = auto()
    OBJ_BY_REF = auto()


@dataclass(frozen=True)
class FieldSpec:
    source: str  # Name of field to copy data from
    destination: str  # Name of field to copy data to
    required: bool = False
    filter: Optional[Callable[[any], bool]] = None
    if_different: Optional[str] = None  # Only copy if it is different to this other field (before conversion)
    convert: Optional[Callable[[any], any]] = None
