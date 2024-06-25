from .spec import SourceType, DestinationType
from .raw_spec import RawSourceType, RawDestinationType
from .errors import ConvertStructCompileError


def parse_source_type(raw_source_type: RawSourceType) -> SourceType:
    if raw_source_type in {'dict'}:
        return SourceType.DICT
    elif raw_source_type in {'obj', 'object', 'class'}:
        return SourceType.OBJ
    else:
        raise ConvertStructCompileError(f"Invalid source type: {raw_source_type!r}")


def parse_destination_type(raw_dest_type: RawDestinationType) -> DestinationType:
    if raw_dest_type in {'dict'}:
        return DestinationType.DICT
    elif raw_dest_type in {'&dict', '@dict', 'dict-by-ref', 'dict-by-reference'}:
        return DestinationType.DICT_BY_REF
    elif raw_dest_type in {
        '&obj', '@obj', 'obj-by-ref', 'obj-by-reference',
        '&object', '@object', 'object-by-ref', 'object-by-reference',
        '&class', '@class', 'class-by-ref', 'class-by-reference'
    }:
        return DestinationType.OBJ_BY_REF
    else:
        raise ConvertStructCompileError(f"Invalid destination type: {raw_dest_type!r}")
