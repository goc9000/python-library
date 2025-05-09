from collections.abc import Mapping, Sequence, Hashable, Iterable, Set
from typing import Optional, TypeVar, Callable, Any, Union, Type

from .spec import ConversionSpec, SourceType, SourceSpec, DestinationType, DestinationSpec, FieldSpec, ConstSpec
from .raw_spec import RawSourceType, RawDestinationType, RawFieldSpec, RawFieldSpecs, NormalizedRawFieldSpec
from .errors import ConvertStructCompileError


def parse_conversion_spec(
    raw_source_type: RawSourceType, raw_dest_type: RawDestinationType, raw_fields: RawFieldSpecs,
    ignore: Iterable[str] = (), return_unparsed: bool = False, none_means_missing: bool = True,
    dest_by_reference: bool = False
) -> ConversionSpec:
    fields, ignored_fields = parse_fields(raw_fields)

    return ConversionSpec(
        source=parse_source_spec(raw_source_type),
        destination=parse_destination_spec(raw_dest_type, dest_by_reference),
        fields=fields,
        ignored_fields=frozenset([*ignored_fields, *ignore]),
        return_unparsed=return_unparsed,
        none_means_missing=none_means_missing,
    )


def parse_source_spec(raw_source_type: RawSourceType) -> SourceSpec:
    if raw_source_type in {'dict', dict}:
        return SourceSpec(type=SourceType.DICT)
    elif raw_source_type in {'obj', 'object', object, 'class'}:
        return SourceSpec(type=SourceType.OBJ)
    elif isinstance(raw_source_type, Type):
        return SourceSpec(type=SourceType.OBJ, class_=raw_source_type)
    else:
        raise ConvertStructCompileError(f"Invalid source type: {raw_source_type!r}")


def parse_destination_spec(raw_dest_type: RawDestinationType, dest_by_reference: bool = False) -> DestinationSpec:
    if raw_dest_type in {'dict', dict}:
        return DestinationSpec(type=DestinationType.DICT, by_ref=False)
    elif isinstance(raw_dest_type, Type):
        return DestinationSpec(type=DestinationType.OBJ, class_=raw_dest_type, by_ref=dest_by_reference)
    elif raw_dest_type in {'&dict', '@dict', 'dict-by-ref', 'dict-by-reference'}:
        return DestinationSpec(type=DestinationType.DICT, by_ref=True)
    elif raw_dest_type in {
        '&obj', '@obj', 'obj-by-ref', 'obj-by-reference',
        '&object', '@object', 'object-by-ref', 'object-by-reference',
        '&class', '@class', 'class-by-ref', 'class-by-reference'
    }:
        return DestinationSpec(type=DestinationType.OBJ, by_ref=False)
    else:
        raise ConvertStructCompileError(f"Invalid destination type: {raw_dest_type!r}")


def parse_fields(fields: RawFieldSpecs) -> tuple[tuple[FieldSpec, ...], Set[str]]:
    out_fields = []
    ignored_fields = set()

    for field, raw_field_spec in fields.items():
        try:
            parsed_field_spec = parse_field_spec(raw_field_spec, field)

            if parsed_field_spec is not None:
                out_fields.append(parsed_field_spec)
            else:
                ignored_fields.add(field)
        except Exception as e:
            raise ConvertStructCompileError(f"Invalid field spec for field '{field}'") from e

    return tuple(out_fields), frozenset(ignored_fields)


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


def parse_field_spec(raw_field_spec: RawFieldSpec, destination: str) -> Optional[FieldSpec]:
    if isinstance(raw_field_spec, FieldSpec):
        return raw_field_spec

    destination = _expect_field_name(destination)
    normalized_raw_field_spec = normalize_raw_field_spec(raw_field_spec)

    if 'ignore' in normalized_raw_field_spec:
        if not normalized_raw_field_spec['ignore']:
            raise ConvertStructCompileError("If 'ignore' is set, it must be True")
        if len(normalized_raw_field_spec) > 1:
            raise ConvertStructCompileError("If 'ignore' is set, it must be the only key")

        return None

    if ('store' in normalized_raw_field_spec) and ('convert' in normalized_raw_field_spec):
        raise ConvertStructCompileError("The 'store' and 'convert' parameters are mutually exclusive")

    init_params = dict(destination=destination, source=destination)

    # How ironic that the struct converter itself would be excellent at doing the job of the following code!
    # Chicken and the egg...

    for key, value in normalized_raw_field_spec.items():
        try:
            if key == 'src':
                init_params['source'] = _expect_field_name(value)
            elif key == 'if_different':
                init_params[key] = _expect_field_name(value)
            elif key == 'req':
                init_params['required'] = _typecheck(value, bool)
            elif key == 'skip_empty':
                if _typecheck(value, bool):
                    init_params['skip_empty'] = True
            elif key == 'skip_if':
                init_params[key] = _parse_skip_if_set(value)
            elif key == 'convert':
                init_params[key] = _parse_converter(value)
            elif key in ('store', 'default'):
                init_params[key] = _parse_const(value)
            else:
                raise KeyError("Don't recognize this field")
        except Exception as e:
            raise ConvertStructCompileError(f"Invalid field spec parameter '{key}'") from e

    return FieldSpec(**init_params)


def _expect_field_name(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Field name expected, got {type(value).__name__}")
    if str == '':
        raise ValueError("Field name cannot be empty")

    return value


T = TypeVar('T')


def _typecheck(value: T, expected_type) -> T:
    if not isinstance(value, expected_type):
        raise TypeError(f"Expected {expected_type}, got {type(value).__name__}")

    return value


def _parse_skip_if_set(value_or_values: Union[Hashable, list[Hashable], set[Hashable]]) -> Set[Hashable]:
    if isinstance(value_or_values, (list, set)):
        for value in value_or_values:
            _typecheck(value, Hashable)

        return frozenset(value_or_values)

    _typecheck(value_or_values, Hashable)

    return frozenset([value_or_values])


def _parse_converter(converter_spec: Union[Callable[[Any], Any], str]) -> Callable[[Any], Any]:
    _typecheck(converter_spec, (str, Callable))

    if not isinstance(converter_spec, str):
        return converter_spec

    if converter_spec == 'utf8':
        return lambda x: x.decode('utf-8')
    elif converter_spec == 'hex':
        return lambda x: x.hex()

    raise ValueError(f"Unknown built-in converter: '{converter_spec}'")


def _parse_const(value: Union[Hashable, Type, Callable[[], Any]]) -> ConstSpec:
    if isinstance(value, Type) or callable(value):
        return ConstSpec(factory=value)

    _typecheck(value, Hashable)

    return ConstSpec(constant=value)
