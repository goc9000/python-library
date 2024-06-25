from typing import Mapping, Sequence

from .spec import SourceType, DestinationType
from .raw_spec import RawSourceType, RawDestinationType, RawFieldSpec, NormalizedRawFieldSpec
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


def normalize_raw_field_spec(raw_field_spec: RawFieldSpec) -> NormalizedRawFieldSpec:
    if (raw_field_spec is None) or (raw_field_spec is True):
        return dict()
    if raw_field_spec is False:
        return dict(ignore=True)
    if isinstance(raw_field_spec, Mapping):
        return raw_field_spec
    if isinstance(raw_field_spec, str):
        return {raw_field_spec: True} if raw_field_spec != '' else dict()
    if isinstance(raw_field_spec, Sequence):
        result = dict()

        for part in raw_field_spec:
            for k, v in normalize_raw_field_spec(part).items():
                if k in result:
                    raise ConvertStructCompileError(f"Parameter '{k}' is specified more than once")
                result[k] = v

        return result

    raise ConvertStructCompileError(f"Can't parse field spec of type {type(raw_field_spec).__name__}")
