import re

from collections.abc import Set
from collections import Counter
from contextlib import contextmanager
from typing import Callable, Optional, NamedTuple, Type

from atmfjstc.lib.py_lang_utils.token import Token
from atmfjstc.lib.py_lang_utils.data_objs import get_obj_likely_data_fields_with_defaults

from .spec import ConversionSpec, SourceType, SourceSpec, DestinationType, DestinationSpec, FieldSpec, ConstSpec
from .errors import ConvertStructCompileError, ConvertStructWrongSourceTypeError, ConvertStructMissingRequiredFieldError


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
        source = _compile_setup_source(context, spec)
        destination = _compile_setup_destination(context, spec.destination)

        for field in spec.fields:
            _compile_field_conversion_core(context, field, destination, source)

        return_values = _compile_return_values(context, destination)

        if spec.return_unparsed:
            _compile_unhandled_getter(context, spec.source, spec.fields, spec.ignored_fields)
            return_values.append('unhandled_fields')

        if len(return_values) > 0:
            context.add_line(f"return {', '.join(return_values)}")

    return context.render(), context.globals


class _DestinationInfo(NamedTuple):
    spec: DestinationSpec
    type_for_set: DestinationType
    variable: str


class _SourceInfo(NamedTuple):
    spec: SourceSpec
    variable: str
    none_means_missing: bool


class _CompileContext:
    globals: dict

    _lines: list[str]
    _indent: int = 0
    _discriminants: Counter[str]

    def __init__(self):
        self.globals = dict()
        self._lines = []
        self._discriminants = Counter()

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

    def expose_type(self, cls: Type) -> str:
        if cls.__name__ in dir(__builtins__):
            return cls.__name__

        self.globals[cls.__name__] = cls

        return cls.__name__

    def expose_new(self, prefix: str, value) -> str:
        var_name = f"{prefix}_{self._discriminants[prefix]}"

        self.globals[var_name] = value
        self._discriminants[prefix] += 1

        return var_name


def _compile_converter_params(destination_spec: DestinationSpec) -> tuple[str, ...]:
    return ('mut_dest', 'source') if destination_spec.by_ref else ('source',)


def _compile_setup_source(context: _CompileContext, spec: ConversionSpec) -> _SourceInfo:
    if spec.source.class_ is not None:
        src_class_repr = context.expose_type(spec.source.class_)

        with context.indent(f"if not isinstance(source, {src_class_repr}):"):
            context.add_line(
                f"raise {context.expose_type(ConvertStructWrongSourceTypeError)}({src_class_repr}, source.__class__)"
            )

    return _SourceInfo(spec=spec.source, variable='source', none_means_missing=spec.none_means_missing)


def _compile_setup_destination(context: _CompileContext, destination_spec: DestinationSpec) -> _DestinationInfo:
    if destination_spec.by_ref:
        destination_var = 'mut_dest'
        type_for_set = destination_spec.type
    else:
        if destination_spec.type == DestinationType.DICT:
            context.add_line('destination = dict()')
            destination_var = 'destination'
            type_for_set = DestinationType.DICT
        elif destination_spec.type == DestinationType.OBJ:
            context.add_line('staging = dict()')
            destination_var = 'staging'
            type_for_set = DestinationType.DICT
        else:
            raise AssertionError(f"Unhandled destination type: {destination_spec.type}")

    return _DestinationInfo(spec=destination_spec, variable=destination_var, type_for_set=type_for_set)


def _compile_get_field(context: _CompileContext, source: _SourceInfo, field: str, temp_name: str = 'value') -> str:
    context.globals['_NO_VALUE'] = _NO_VALUE

    if source.spec.type == SourceType.DICT:
        result = f"{source.variable}.get({field!r}, _NO_VALUE)"
    elif source.spec.type == SourceType.OBJ:
        result = f"getattr({source.variable}, {field!r}, _NO_VALUE)"
    else:
        raise AssertionError(f"Unhandled source type: {source.spec.type}")

    if source.none_means_missing:
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
    if destination.type_for_set == DestinationType.DICT:
        context.add_line(f"{destination.variable}[{field!r}] = {value_expr}")
    elif destination.type_for_set == DestinationType.OBJ:
        context.add_line(f"setattr({destination.variable}, {field!r}, {value_expr})")
    else:
        raise AssertionError(f"Unhandled destination type: {destination.type_for_set}")


def _compile_return_values(context: _CompileContext, destination: _DestinationInfo) -> list[str]:
    if destination.spec.by_ref:
        return []

    if destination.spec.type == DestinationType.DICT:
        return [destination.variable]
    elif destination.spec.type == DestinationType.OBJ:
        return [f"{context.expose_type(destination.spec.class_)}(**{destination.variable})"]
    else:
        raise AssertionError(f"Unhandled destination type: {destination.spec.type}")


def _compile_field_conversion_core(
    context: _CompileContext, field: FieldSpec, destination: _DestinationInfo, source: _SourceInfo
):
    value_expr = _compile_get_field(context, source, field.source)
    value_var = _drop_to_variable(context, value_expr, 'value')

    if field.required:
        with context.indent(f"if {value_var} is _NO_VALUE:"):
            context.add_line(f"raise {context.expose_type(ConvertStructMissingRequiredFieldError)}({field.source!r})")

    filters = []

    if not field.required:
        filters.append(dict(
            condition=f"{value_var} is not _NO_VALUE"
        ))

    if field.if_different is not None:
        def _prepare_if_different(ctx: _CompileContext):
            other_value_expr = _compile_get_field(ctx, source, field.if_different, 'other')
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
        filters.append(dict(
            condition=f"{value_var} not in {context.expose_new('skip_if', field.skip_if)}"
        ))

    _compile_conversion_with_filters(
        context, filters,
        _compile_final_setter_code(destination, field, value_var),
        _compile_default_setter_code(destination, field, field.default) if field.default is not None else None,
    )


def _compile_final_setter_code(
    destination: _DestinationInfo, field: FieldSpec, value_var: str
) -> Callable[[_CompileContext], None]:
    def _render_setter(ctx: _CompileContext):
        if field.store is not None:
            if field.store.factory is not None:
                value_expr = f"{ctx.expose_new('factory', field.store.factory)}()"
            else:
                value_expr = f"{ctx.expose_new('const', field.store.constant)}"
        elif field.convert is not None:
            value_expr = f"{ctx.expose_new('converter', field.convert)}({value_var})"
        else:
            value_expr = value_var

        _compile_set_field(ctx, destination, field.destination, value_expr)

    return _render_setter


def _compile_default_setter_code(
    destination: _DestinationInfo, field: FieldSpec, default_spec: ConstSpec
) -> Optional[Callable[[_CompileContext], None]]:
    def _render_setter(ctx: _CompileContext):
        if default_spec.factory is not None:
            value_expr = f"{ctx.expose_new('factory', default_spec.factory)}()"
        else:
            value_expr = f"{ctx.expose_new('const', default_spec.constant)}"

        _compile_set_field(ctx, destination, field.destination, value_expr)

    return _render_setter


def _compile_conversion_with_filters(
    context: _CompileContext, filters: list[dict],
    render_setter: Callable[[_CompileContext], None],
    render_default_setter: Optional[Callable[[_CompileContext], None]]
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
        _compile_conversion_with_filters(context, filters_rest, render_setter, render_default_setter)

    if render_default_setter is not None:
        with context.indent(f"else:"):
            render_default_setter(context)


def _compile_unhandled_getter(
    context: _CompileContext, source_spec: SourceSpec, fields: tuple[FieldSpec, ...], ignored_fields: Set[str]
):
    all_srcs = set(field.source for field in fields) | ignored_fields
    all_srcs_set = ('{' + ', '.join(repr(item) for item in all_srcs) + '}') if len(all_srcs) > 0 else 'set()'

    if source_spec.type == SourceType.DICT:
        context.add_line('unhandled_fields = {k: v for k, v in source.items() if k not in ' + all_srcs_set + '}')
    elif source_spec.type == SourceType.OBJ:
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
        raise AssertionError(f"Unhandled source type: {source_spec.type}")
