import re

from collections.abc import Set
from contextlib import contextmanager
from typing import Callable, Optional, NamedTuple

from atmfjstc.lib.py_lang_utils.token import Token
from atmfjstc.lib.py_lang_utils.data_objs import get_obj_likely_data_fields_with_defaults

from .spec import ConversionSpec, SourceType, DestinationType, DestinationSpec, FieldSpec
from .errors import ConvertStructCompileError


_NO_VALUE = Token()


def compile_converter(spec: ConversionSpec) -> Callable:
    code, globals = _compile_converter(spec)

    try:
        exec(code, globals)

        return globals['convert']
    except Exception as e:
        raise ConvertStructCompileError("Failed to compile converter") from e


def debug_compile_converter(spec: ConversionSpec) -> dict:
    code, globals = _compile_converter(spec)

    return {
        'code': code,
        'globals': globals,
    }


def _compile_converter(spec: ConversionSpec) -> tuple[str, dict]:
    context = _CompileContext()

    parameters = _compile_converter_params(spec.destination)

    with context.indent(f"def convert({', '.join(parameters)}):"):
        if spec.destination.by_ref:
            destination_var = 'mut_dest'
        else:
            context.add_line(f"destination = {_compile_init_destination(spec.destination)}")
            destination_var = 'destination'

        _compile_conversion_core(context, _DestinationInfo(spec=spec.destination, variable=destination_var), spec)

        return_values = _compile_return_values(spec.destination)

        if spec.return_unparsed:
            _compile_unhandled_getter(context, spec.source_type, spec.fields, spec.ignored_fields)
            return_values.append('unhandled_fields')

        if len(return_values) > 0:
            context.add_line(f"return {', '.join(return_values)}")

    return context.render(), context.globals


class _DestinationInfo(NamedTuple):
    spec: DestinationSpec
    variable: str


class _CompileContext:
    globals: dict

    _lines: list[str]
    _indent: int = 0

    def __init__(self):
        self.globals = dict()
        self._lines = []

    def render(self) -> str:
        return "\n".join(self._lines)

    def add_line(self, line: str) -> '_CompileContext':
        self._lines.append(f"{' ' * (self._indent * 4)}{line}")
        return self

    def add_lines(self, *lines: str) -> '_CompileContext':
        for line in lines:
            self.add_line(line)
        return self

    @contextmanager
    def indent(self, header: Optional[str] = None):
        if header is not None:
            self.add_line(header)

        try:
            self._indent += 1
            yield
        finally:
            self._indent -= 1


def _compile_converter_params(destination_spec: DestinationSpec) -> tuple[str, ...]:
    return ('mut_dest', 'source') if destination_spec.by_ref else ('source',)


def _compile_init_destination(destination_spec: DestinationSpec) -> str:
    if destination_spec.type == DestinationType.DICT:
        return 'dict()'
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_spec}")


def _compile_get_field(
    context: _CompileContext, field: str, source_type: SourceType, none_means_missing: bool, temp_name: str = 'value'
) -> str:
    context.globals['_NO_VALUE'] = _NO_VALUE

    if source_type == SourceType.DICT:
        result = f"source.get({field!r}, _NO_VALUE)"
    elif source_type == SourceType.OBJ:
        result = f"getattr(source, {field!r}, _NO_VALUE)"
    else:
        raise ConvertStructCompileError(f"Unsupported source type: {source_type}")

    if none_means_missing:
        _drop_to_variable(context, result, temp_name)
        with context.indent(f"if {temp_name} is None:"):
            context.add_line(f"{temp_name} = _NO_VALUE")
        result = temp_name

    return result


def _drop_to_variable(context: _CompileContext, expr: str, var_name: str) -> str:
    if re.match(r'^[a-z0-9_]+$', expr, re.I):
        return expr

    context.add_line(f"{var_name} = {expr}")

    return var_name


def _compile_set_field(context: _CompileContext, destination: _DestinationInfo, field: str, value_expr: str):
    if destination.spec.type == DestinationType.DICT:
        context.add_line(f"{destination.variable}[{field!r}] = {value_expr}")
    elif destination.spec.type == DestinationType.OBJ:
        context.add_line(f"setattr({destination.variable}, {field!r}, {value_expr})")
    else:
        raise ConvertStructCompileError(f"Unsupported destination info: {destination}")


def _compile_return_values(destination_spec: DestinationSpec) -> list[str]:
    return_values = []

    if destination_spec.by_ref:
        pass
    elif destination_spec.type == DestinationType.DICT:
        return_values.append('destination')
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_spec}")

    return return_values


def _compile_conversion_core(context: _CompileContext, destination: _DestinationInfo, spec: ConversionSpec):
    for index, field in enumerate(spec.fields):
        discriminant = f"_{index}"

        _compile_field_conversion_core(context, field, discriminant, destination, spec)


def _compile_field_conversion_core(
    context: _CompileContext, field: FieldSpec, discriminant: str, destination: _DestinationInfo, spec: ConversionSpec
):
    value_expr = _compile_get_field(context, field.source, spec.source_type, spec.none_means_missing)
    value_var = _drop_to_variable(context, value_expr, 'value')

    if field.required:
        with context.indent(f"if {value_var} is _NO_VALUE:"):
            context.add_line(f"raise ConvertStructMissingRequiredFieldError({field.source!r})")

    filters = []

    if not field.required:
        filters.append(dict(
            condition=f"{value_var} is not _NO_VALUE"
        ))

    if field.if_different is not None:
        def _prepare_if_different(ctx: _CompileContext):
            other_value_expr = \
                _compile_get_field(ctx, field.if_different, spec.source_type, spec.none_means_missing, 'other')
            other_var = _drop_to_variable(ctx, other_value_expr, 'other')

            return f"{value_var} != {other_var}"

        filters.append(dict(
            prepare_condition=_prepare_if_different,
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
        context.globals[f'skip_if{discriminant}'] = field.skip_if

        filters.append(dict(
            condition=f"{value_var} not in skip_if{discriminant}"
        ))

    def _render_setter(ctx: _CompileContext):
        if field.store is not None:
            if field.store.factory is not None:
                context.globals[f'factory{discriminant}'] = field.store.factory
                value_expr = f"factory{discriminant}()"
            else:
                context.globals[f'const{discriminant}'] = field.store.constant
                value_expr = f"const{discriminant}"
        elif field.convert is not None:
            context.globals[f'converter{discriminant}'] = field.convert
            value_expr = f"converter{discriminant}({value_var})"
        else:
            value_expr = value_var

        _compile_set_field(ctx, destination, field.destination, value_expr)

    _compile_conversion_with_filters(context, filters, _render_setter)


def _compile_conversion_with_filters(
    context: _CompileContext, filters: list[dict], render_setter: Callable[[_CompileContext], None]
):
    if len(filters) == 0:
        render_setter(context)
        return

    filter, *filters_rest = filters

    if 'condition' in filter:
        condition = filter['condition']
    else:
        condition = filter['prepare_condition'](context)

    with context.indent(f"if {condition}:"):
        _compile_conversion_with_filters(context, filters_rest, render_setter)


def _compile_unhandled_getter(
    context: _CompileContext, source_type: SourceType, fields: tuple[FieldSpec, ...], ignored_fields: Set[str]
):
    all_srcs = set(field.source for field in fields) | ignored_fields
    all_srcs_set = ('{' + ', '.join(repr(item) for item in all_srcs) + '}') if len(all_srcs) > 0 else 'set()'

    if source_type == SourceType.DICT:
        context.add_line('unhandled_fields = {k: v for k, v in source.items() if k not in ' + all_srcs_set + '}')
    elif source_type == SourceType.OBJ:
        context.globals['get_obj_likely_data_fields_with_defaults'] = get_obj_likely_data_fields_with_defaults

        context.add_line('unhandled_fields = dict()')

        with context.indent(
            'for k in get_obj_likely_data_fields_with_defaults(source, include_properties=False).keys():'
        ):
            with context.indent(f"if k not in {all_srcs_set}:"):
                with context.indent('try:'):
                    context.add_line('unhandled_fields[k] = getattr(source, k)')
                with context.indent('except Exception:'):
                    context.add_line('pass')
    else:
        raise ConvertStructCompileError(f"Unsupported source type: {source_type}")
