from enum import Enum, auto


class SourceType(Enum):
    DICT = auto()
    OBJ = auto()


class DestinationType(Enum):
    DICT = auto()
    DICT_BY_REF = auto()
    OBJ_BY_REF = auto()
