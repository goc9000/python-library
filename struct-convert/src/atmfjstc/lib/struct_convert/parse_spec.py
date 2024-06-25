from collections.abc import Mapping, Sequence, Hashable, Iterable, Set
from typing import Optional, TypeVar, Callable, Any, Union

from .spec import ConversionSpec, SourceType, DestinationType, FieldSpec
from .raw_spec import RawSourceType, RawDestinationType, RawFieldSpec, RawFieldSpecs, NormalizedRawFieldSpec
from .errors import ConvertStructCompileError


def parse_conversion_spec(
    raw_source_type: RawSourceType, raw_dest_type: RawDestinationType, raw_fields: RawFieldSpecs,
    ignore: Iterable[str] = (), return_unparsed: bool = False, none_means_missing: bool = True
) -> ConversionSpec:
    fields, ignored_fields = parse_fields(raw_fields)

    return ConversionSpec(
        source_type=parse_source_type(raw_source_type),
        destination_type=parse_destination_type(raw_dest_type),
        fields=fields,
        ignored_fields=frozenset([*ignored_fields, *ignore]),
        return_unparsed=return_unparsed,
        none_means_missing=none_means_missing,
    )


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
    filters = []

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
                    filters.append((1, _is_nonempty))
            elif key == 'skip_if':
                filters.append((2, _make_not_eq_filter(value)))
            elif key == 'convert':
                init_params[key] = _parse_converter(value)
            elif key == 'store':
                init_params['convert'] = _parse_store(value)
            else:
                raise KeyError("Don't recognize this field")
        except Exception as e:
            raise ConvertStructCompileError(f"Invalid field spec parameter '{key}'") from e

    if len(filters) > 0:
        init_params['filter'] = lambda x: all(filt(x) for _, filt in sorted(filters, key=lambda pair: pair[0]))

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


def _is_nonempty(value: Any) -> bool:
    return not (
        (value is False) or (value is None) or (isinstance(value, int) and (value == 0)) or
        (hasattr(value, '__len__') and (len(value) == 0))
    )


def _make_not_eq_filter(value: Any) -> Callable[[Any], bool]:
    return lambda x: x != value


def _parse_converter(converter_spec: Union[Callable[[Any], Any], str]) -> Callable[[Any], Any]:
    _typecheck(converter_spec, (str, Callable))

    if not isinstance(converter_spec, str):
        return converter_spec

    if converter_spec == 'utf8':
        return lambda x: x.decode('utf-8')
    elif converter_spec == 'hex':
        return lambda x: x.hex()

    raise ValueError(f"Unknown built-in converter: '{converter_spec}'")


def _parse_store(value: Hashable) -> Callable[[Any], Any]:
    _typecheck(value, Hashable)

    try:
        _ = hash(value)
    except Exception:
        raise TypeError("Only constant (hashable) values may be stored") from None

    return lambda _: value
