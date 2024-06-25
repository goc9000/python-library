from collections.abc import Set
from typing import Callable, Any, Tuple, Union
from collections.abc import Mapping

from atmfjstc.lib.py_lang_utils.token import Token
from atmfjstc.lib.py_lang_utils.data_objs import get_obj_likely_data_fields_with_defaults

from .spec import ConversionSpec, SourceType, DestinationType, DestinationSpec, FieldSpec
from .errors import ConvertStructCompileError, ConvertStructMissingRequiredFieldError


_NO_VALUE = Token()


def compile_converter(spec: ConversionSpec) -> Callable:
    unhandled_getter = _setup_unhandled_getter(spec.source_type, spec.fields, spec.ignored_fields)
    getter = _setup_field_getter(spec.source_type, spec.none_means_missing)
    setter = _setup_field_setter(spec.destination)

    converter_core = _setup_conversion_core(spec.fields, getter, setter)

    parameters = _compile_converter_params(spec.destination)
    return_values = _compile_return_values(spec.destination, spec.return_unparsed)

    func_header = f"def convert({', '.join(parameters)}):"
    code_lines = []

    globals = dict(
        converter_core=converter_core,
        unhandled_getter=unhandled_getter,
    )

    code_lines.append(f"source, destination = {', '.join(_compile_source_dest_finder(spec.destination))}")
    code_lines.append(f"source, destination = converter_core(source, destination)")
    code_lines.append(f"return {', '.join(return_values)}")

    code = "\n".join([func_header, *(f"    {line}" for line in code_lines)])

    try:
        exec(code, globals)

        return globals['convert']
    except Exception as e:
        raise ConvertStructCompileError("Failed to compile converter") from e


def _compile_converter_params(destination_spec: DestinationSpec) -> tuple[str, ...]:
    return ('mut_dest', 'source') if destination_spec.by_ref else ('source',)


ParsedFieldSpecs = tuple[FieldSpec, ...]
UnhandledGetter = Callable[[Mapping], dict]
SourceDestFinder = Callable[..., Tuple[Any, Any]]
FieldGetter = Callable[[Any, str], Any]
FieldSetter = Callable[[Any, str, Any], None]
ConvertReturnValue = Union[None, dict, Any, Tuple[Any, dict]]
ResultExtractor = Callable[[Any, Any], ConvertReturnValue]


def _setup_unhandled_getter(
    source_type: SourceType, fields: ParsedFieldSpecs, ignored_fields: Set[str]
) -> UnhandledGetter:
    all_srcs = set(field.source for field in fields) | ignored_fields

    def _dict_unhandled_getter(source_dict):
        return {k: v for k, v in source_dict.items() if k not in all_srcs}

    def _obj_unhandled_getter(source_obj):
        result = dict()

        for k in get_obj_likely_data_fields_with_defaults(source_obj, include_properties=False).keys():
            if k not in all_srcs:
                try:
                    result[k] = getattr(source_obj, k)
                except Exception:
                    pass

        return result

    if source_type == SourceType.DICT:
        return _dict_unhandled_getter
    elif source_type == SourceType.OBJ:
        return _obj_unhandled_getter
    else:
        raise ConvertStructCompileError(f"Unsupported source type: {source_type}")


def _compile_source_dest_finder(destination_spec: DestinationSpec) -> tuple[str, str]:
    if destination_spec.by_ref:
        return 'source', 'mut_dest'
    elif destination_spec.type == DestinationType.DICT:
        return 'source', 'dict()'
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_spec}")


def _setup_field_getter(source_type: SourceType, none_means_missing: bool) -> FieldGetter:
    def _dict_getter(source_dict, field):
        return source_dict.get(field, _NO_VALUE)

    def _obj_getter(source_obj, field):
        return getattr(source_obj, field, _NO_VALUE)

    if source_type == SourceType.DICT:
        base_getter = _dict_getter
    elif source_type == SourceType.OBJ:
        base_getter = _obj_getter
    else:
        raise ConvertStructCompileError(f"Unsupported source type: {source_type}")

    if not none_means_missing:
        return base_getter

    def _adjust_nones(source, field):
        value = base_getter(source, field)
        return value if value is not None else _NO_VALUE

    return _adjust_nones


def _setup_field_setter(destination_spec: DestinationSpec) -> FieldSetter:
    def _dict_setter(dest_dict, field, value):
        dest_dict[field] = value

    def _obj_setter(dest_obj, field, value):
        setattr(dest_obj, field, value)

    if destination_spec.type == DestinationType.DICT:
        return _dict_setter
    elif destination_spec.type == DestinationType.OBJ:
        return _obj_setter
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_spec}")


def _compile_return_values(destination_spec: DestinationSpec, return_unparsed_option: bool) -> list[str]:
    if destination_spec.by_ref:
        if return_unparsed_option:
            return ['unhandled_getter(source)']
        else:
            return ['None']
    elif destination_spec.type == DestinationType.DICT:
        if return_unparsed_option:
            return ['destination', 'unhandled_getter(source)']
        else:
            return ['destination']
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_spec}")


def _setup_conversion_core(fields: ParsedFieldSpecs, getter: FieldGetter, setter: FieldSetter) -> Callable:
    def _convert_core(source, destination):
        field_getter = lambda field_name: getter(source, field_name)

        for field_spec in fields:
            value = do_convert(field_spec, field_getter)

            if value is not _NO_VALUE:
                setter(destination, field_spec.destination, value)

        return source, destination

    return _convert_core


def do_convert(field_spec: FieldSpec, field_getter: Callable[[str], Any]) -> Any:
    value = field_getter(field_spec.source)

    if value is _NO_VALUE:
        if field_spec.required:
            raise ConvertStructMissingRequiredFieldError(field_spec.source)

        return _NO_VALUE

    if (field_spec.filter is not None) and not field_spec.filter(value):
        return _NO_VALUE
    if (field_spec.if_different is not None) and (value == field_getter(field_spec.if_different)):
        return _NO_VALUE

    if field_spec.convert is not None:
        value = field_spec.convert(value)

    return value
