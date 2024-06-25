import re

from collections.abc import Set
from typing import Callable, Any
from collections.abc import Mapping

from atmfjstc.lib.py_lang_utils.token import Token
from atmfjstc.lib.py_lang_utils.data_objs import get_obj_likely_data_fields_with_defaults

from .spec import ConversionSpec, SourceType, DestinationType, DestinationSpec, FieldSpec
from .errors import ConvertStructCompileError, ConvertStructMissingRequiredFieldError


_NO_VALUE = Token()


def compile_converter(spec: ConversionSpec) -> Callable:
    parameters = _compile_converter_params(spec.destination)

    func_header = f"def convert({', '.join(parameters)}):"
    code_lines = []

    globals = dict()

    if spec.destination.by_ref:
        destination_var = 'mut_dest'
    else:
        code_lines.append(f"destination = {_compile_init_destination(spec.destination)}")
        destination_var = 'destination'

    _compile_conversion_core(code_lines, globals, destination_var, spec)

    return_values = _compile_return_values(spec.destination)

    if spec.return_unparsed:
        _compile_unhandled_getter(code_lines, globals, spec.source_type, spec.fields, spec.ignored_fields)
        return_values.append('unhandled_fields')

    if len(return_values) > 0:
        code_lines.append(f"return {', '.join(return_values)}")

    code = "\n".join([func_header, *(f"    {line}" for line in code_lines)])

    try:
        exec(code, globals)

        return globals['convert']
    except Exception as e:
        raise ConvertStructCompileError("Failed to compile converter") from e


def _compile_converter_params(destination_spec: DestinationSpec) -> tuple[str, ...]:
    return ('mut_dest', 'source') if destination_spec.by_ref else ('source',)


FieldGetter = Callable[[Any, str], Any]


def _compile_unhandled_getter(
    mut_code_lines: list[str], mut_globals: dict,
    source_type: SourceType, fields: tuple[FieldSpec, ...], ignored_fields: Set[str]
):
    all_srcs = set(field.source for field in fields) | ignored_fields
    all_srcs_set = ('{' + ', '.join(repr(item) for item in all_srcs) + '}') if len(all_srcs) > 0 else 'set()'

    if source_type == SourceType.DICT:
        mut_code_lines.append('unhandled_fields = {k: v for k, v in source.items() if k not in ' + all_srcs_set + '}')
    elif source_type == SourceType.OBJ:
        mut_globals['get_obj_likely_data_fields_with_defaults'] = get_obj_likely_data_fields_with_defaults

        mut_code_lines.extend([
            'unhandled_fields = dict()',
            'for k in get_obj_likely_data_fields_with_defaults(source, include_properties=False).keys():',
            f"    if k not in {all_srcs_set}:",
            '        try:',
            '            unhandled_fields[k] = getattr(source, k)',
            '        except Exception:',
            '            pass',
        ])
    else:
        raise ConvertStructCompileError(f"Unsupported source type: {source_type}")


def _compile_init_destination(destination_spec: DestinationSpec) -> str:
    if destination_spec.type == DestinationType.DICT:
        return 'dict()'
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


def _compile_set_field(
    mut_code_lines: list[str], destination_var: str, destination_spec: DestinationSpec, field: str, value_expr: str
):
    if destination_spec.type == DestinationType.DICT:
        mut_code_lines.append(f"{destination_var}[{field!r}] = {value_expr}")
    elif destination_spec.type == DestinationType.OBJ:
        mut_code_lines.append(f"setattr({destination_var}, {field!r}, {value_expr})")
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_spec}")


def _compile_return_values(destination_spec: DestinationSpec) -> list[str]:
    return_values = []

    if destination_spec.by_ref:
        pass
    elif destination_spec.type == DestinationType.DICT:
        return_values.append('destination')
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_spec}")

    return return_values


def _compile_conversion_core(mut_code_lines: list[str], mut_globals: dict, destination_var: str, spec: ConversionSpec):
    getter = _setup_field_getter(spec.source_type, spec.none_means_missing)

    for index, field in enumerate(spec.fields):
        value_expr = _compile_get_field(
            mut_code_lines, mut_globals, field.source, spec.source_type, spec.none_means_missing
        )
        value_var = _drop_to_variable(mut_code_lines, value_expr, 'value')

        lines_if_value = []
        mut_globals[f'converter_core{index}'] = _setup_conversion_core_for_field(field, getter)

        lines_if_value.append(f"{value_var} = converter_core{index}(source, {value_var})")

        lines_if_value.append(f"if {value_var} is not _NO_VALUE:")
        setter_lines = []
        _compile_set_field(setter_lines, destination_var, spec.destination, field.destination, value_var)
        lines_if_value.extend(f"    {line}" for line in setter_lines)

        if field.required:
            mut_code_lines.append(f"if {value_var} is _NO_VALUE:")
            mut_code_lines.append(f"    raise ConvertStructMissingRequiredFieldError({field.source!r})")
            mut_code_lines.extend(lines_if_value)
        else:
            mut_code_lines.append(f"if {value_var} is not _NO_VALUE:")
            mut_code_lines.extend(f"    {line}" for line in lines_if_value)


def _compile_get_field(
    mut_code_lines: list[str], mut_globals: dict, field: str, source_type: SourceType, none_means_missing: bool,
    temp_name: str = 'value'
) -> str:
    mut_globals['_NO_VALUE'] = _NO_VALUE

    if source_type == SourceType.DICT:
        result = f"source.get({field!r}, _NO_VALUE)"
    elif source_type == SourceType.OBJ:
        result = f"getattr(source, {field!r}, _NO_VALUE)"
    else:
        raise ConvertStructCompileError(f"Unsupported source type: {source_type}")

    if none_means_missing:
        _drop_to_variable(mut_code_lines, result, temp_name)
        mut_code_lines.append(f"if {temp_name} is None:")
        mut_code_lines.append(f"     {temp_name} = _NO_VALUE")
        result = temp_name

    return result


def _drop_to_variable(mut_code_lines: list[str], expr: str, var_name: str) -> str:
    if re.match(r'^[a-z0-9_]+$', expr, re.I):
        return expr

    mut_code_lines.append(f"{var_name} = {expr}")

    return var_name


def _setup_conversion_core_for_field(field_spec: FieldSpec, getter: FieldGetter) -> Callable:
    def _convert_core(source, obtained_value):
        field_getter = lambda field_name: getter(source, field_name)

        return do_convert(field_spec, field_getter, obtained_value)

    return _convert_core


def do_convert(field_spec: FieldSpec, field_getter: Callable[[str], Any], obtained_value: Any) -> Any:
    value = obtained_value

    if (field_spec.filter is not None) and not field_spec.filter(value):
        return _NO_VALUE
    if (field_spec.if_different is not None) and (value == field_getter(field_spec.if_different)):
        return _NO_VALUE

    if field_spec.convert is not None:
        value = field_spec.convert(value)

    return value
