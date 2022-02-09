"""
Helpers for easier building of JSON schemas in Python code.

Import this using, e.g.::

    import atmfjstc.lib.json_schema_utils.definition_helpers as SH

then define schemas using the helpers like e.g.::

    MY_SCHEMA = SH.one_of(
        SH.integer(maximum=3),
        SH.regex('^[A-Z]+$')
    )
"""

from typing import Optional, Iterable, List, Dict, Union

from atmfjstc.lib.py_lang_utils.dict import dict_no_nulls
from atmfjstc.lib.json_schema_utils import JSONSchema


def nul() -> JSONSchema:
    return dict_no_nulls(type='null')


def lit(value: Union[None, int, float, str, bool]) -> JSONSchema:
    return dict(const=value)


def enu(values: Iterable[Union[None, int, float, str, bool]]) -> JSONSchema:
    return dict(enum=list(values))


def boolean(default: Optional[bool] = None) -> JSONSchema:
    return dict_no_nulls(type='boolean', default=default)


def integer(min: Optional[int] = None, max: Optional[int] = None, default: Optional[int] = None) -> JSONSchema:
    return dict_no_nulls(type='integer', minimum=min, maximum=max, default=default)


def uint(max: Optional[int] = None, default: Optional[int] = None) -> JSONSchema:
    return integer(min=0, max=max, default=default)


def nat(max: Optional[int] = None, default: Optional[int] = None) -> JSONSchema:
    return integer(min=1, max=max, default=default)


def uint8(default: Optional[int] = None) -> JSONSchema:
    return uint(max=(1 << 8) - 1, default=default)


def sint8(default: Optional[int] = None) -> JSONSchema:
    return integer(min=-(1 << 7), max=(1 << 7) - 1, default=default)


def uint16(default: Optional[int] = None) -> JSONSchema:
    return uint(max=(1 << 16) - 1, default=default)


def sint16(default: Optional[int] = None) -> JSONSchema:
    return integer(min=-(1 << 15), max=(1 << 15) - 1, default=default)


def uint32(default: Optional[int] = None) -> JSONSchema:
    return uint(max=(1 << 32) - 1, default=default)


def sint32(default: Optional[int] = None) -> JSONSchema:
    return integer(min=-(1 << 31), max=(1 << 31) - 1, default=default)


def string(min_len: Optional[int] = None, max_len: Optional[int] = None, default: Optional[str] = None) -> JSONSchema:
    return dict_no_nulls(type='string', minLength=min_len, maxLength=max_len, default=default)


def non_empty_str(default: Optional[str] = None) -> JSONSchema:
    return dict_no_nulls(type='string', minLength=1, default=default)


def regex(pattern: str, default: Optional[str] = None) -> JSONSchema:
    return dict_no_nulls(type='string', pattern=pattern, default=default)


def array(
    item_type: JSONSchema, min_length: Optional[str] = None, max_length: Optional[str] = None,
    default: Optional[List] = None
) -> JSONSchema:
    return dict_no_nulls(
        type='array',
        items=item_type,
        minItems=min_length,
        maxItems=max_length,
        default=default,
    )


def tup(*item_types: Iterable[JSONSchema], default: Optional[List] = None) -> JSONSchema:
    item_types = list(item_types)

    return dict_no_nulls(
        type='array',
        items=item_types,
        minItems=len(item_types),
        maxItems=len(item_types),
        default=default,
    )


def obj(
    props: Optional[Dict[str, JSONSchema]] = None,
    optional: Optional[Dict[str, JSONSchema]] = None,
    open: bool = False
) -> JSONSchema:
    props = props or {}
    optional = optional or {}

    schema = dict(
        type='object',
        properties={**props, **optional},
    )

    if len(props or {}) > 0:
        schema['required'] = list(props.keys())
    if not open:
        schema['additionalProperties'] = False

    return schema


def map(value_type: JSONSchema, key_type: Optional[JSONSchema] = None) -> JSONSchema:
    return dict_no_nulls(
        type='object',
        additionalProperties=value_type,
        propertyNames=key_type,
    )


def all_of(*alternatives: Iterable[JSONSchema]) -> JSONSchema:
    return dict(allOf=list(alternatives))


def any_of(*alternatives: Iterable[JSONSchema]) -> JSONSchema:
    return dict(anyOf=list(alternatives))


def one_of(*alternatives: Iterable[JSONSchema]) -> JSONSchema:
    return dict(oneOf=list(alternatives))


def title(title: str, schema: JSONSchema) -> JSONSchema:
    return {**schema, title: title}
