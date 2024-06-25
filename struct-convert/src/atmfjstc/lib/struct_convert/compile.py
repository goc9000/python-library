import re

from collections.abc import Set
from typing import Callable

from atmfjstc.lib.py_lang_utils.token import Token
from atmfjstc.lib.py_lang_utils.data_objs import get_obj_likely_data_fields_with_defaults

from .spec import ConversionSpec, SourceType, DestinationType, DestinationSpec, FieldSpec
from .errors import ConvertStructCompileError


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


def _compile_init_destination(destination_spec: DestinationSpec) -> str:
    if destination_spec.type == DestinationType.DICT:
        return 'dict()'
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_spec}")


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
    for index, field in enumerate(spec.fields):
        value_expr = _compile_get_field(
            mut_code_lines, mut_globals, field.source, spec.source_type, spec.none_means_missing
        )
        value_var = _drop_to_variable(mut_code_lines, value_expr, 'value')

        if field.required:
            mut_code_lines.append(f"if {value_var} is _NO_VALUE:")
            mut_code_lines.append(f"    raise ConvertStructMissingRequiredFieldError({field.source!r})")

        filters = []

        if not field.required:
            filters.append(dict(
                condition=f"{value_var} is not _NO_VALUE"
            ))

        if field.if_different is not None:
            setup_lines = []
            other_value_expr = _compile_get_field(
                setup_lines, mut_globals, field.if_different, spec.source_type, spec.none_means_missing, 'other'
            )
            other_var = _drop_to_variable(setup_lines, other_value_expr, 'other')

            filters.append(dict(
                setup=setup_lines,
                condition=f"{value_var} != {other_var}"
            ))

        if field.skip_empty:
            empty_conditions = [
                f"{value_var} is False",
                f"{value_var} is None",
                f"isinstance({value_var}, int) and (value == 0)",
                f"hasattr({value_var}, '__len__') and (len(value) == 0)",
            ]

            filters.append(dict(
                condition=f"not (({') or ('.join(empty_conditions)}))"
            ))

        if len(field.skip_if) > 0:
            mut_globals[f'skip_if{index}'] = field.skip_if

            filters.append(dict(
                condition=f"{value_var} not in skip_if{index}"
            ))

        setter_lines = []

        if field.store is not None:
            if field.store.factory is not None:
                mut_globals[f'factory{index}'] = field.store.factory
                value_expr = f"factory{index}()"
            else:
                mut_globals[f'const{index}'] = field.store.constant
                value_expr = f"const{index}"
        elif field.convert is not None:
            mut_globals[f'converter{index}'] = field.convert
            value_expr = f"converter{index}({value_var})"
        else:
            value_expr = value_var

        _compile_set_field(setter_lines, destination_var, spec.destination, field.destination, value_expr)

        _compile_conversion_with_filters(mut_code_lines, filters, setter_lines)


def _compile_conversion_with_filters(mut_code_lines: list[str], filters: list[dict], setter_lines: list[str]):
    if len(filters) == 0:
        mut_code_lines.extend(setter_lines)
        return

    filter, *filters_rest = filters

    mut_code_lines.extend(filter.get('setup', []))

    mut_code_lines.append(f"if {filter['condition']}:")

    sub_lines = []
    _compile_conversion_with_filters(sub_lines, filters_rest, setter_lines)

    mut_code_lines.extend(f"    {line}" for line in sub_lines)


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
