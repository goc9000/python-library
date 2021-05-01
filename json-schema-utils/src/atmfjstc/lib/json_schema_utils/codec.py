"""
Central point for registering functions that convert classes to and from JSON data, with the possibility of using
JSON schemas to increase the legibility and reliability of the conversion.
"""

import jsonschema

from functools import singledispatch
from typing import NamedTuple, Tuple

from typing import Type, TypeVar, Any, Callable, Optional, Dict

from atmfjstc.lib.json_schema_utils.definition_helpers import JSONSchema


T = TypeVar('T')


@singledispatch
def to_json(item):
    """
    Main function for converting classes to JSON data. To register a converter, use::

        @to_json.register
        def _(item: ClassToConvert) -> dict:  # Or something else
            ...converter code here...
    """
    raise NotImplementedError(f"Don't know how to format object of type {item.__class__.__name__}")


def from_json(json_data, cls: Type[T], pre_validated: bool = False, tag: Any = None) -> T:
    """
    Main function for parsing JSON data to a corresponding class. See `register_parser()` for details on registering a
    parser.

    The parser is selected either according to the class `cls`, or by the (`cls`, `tag`) combo, if `tag` is provided and
    not None.

    The parser throws:
    - `NoParserRegistered` if no parser is registered for the given class (or class/tag combo)
    - `jsonschema.exceptions.ValidationError` if the data does not match the exception schema
    - Any other exceptions thrown by the parser function itself
    """

    entry = PARSER_REGISTRY.get((cls, tag))
    if entry is None:
        raise NoParserRegistered(cls, tag)

    if entry.schema is not None and not pre_validated:
        jsonschema.validate(json_data, entry.schema)

    return entry.parser(json_data)


def register_parser(
    cls: Type[T],
    schema: Optional[JSONSchema] = None,
    tag: Any = None,
) -> Callable[[Callable[[Any], T]], Callable[[Any], T]]:
    """
    Use this as a decorator for functions that parse from JSON to a given class, e.g.::

        @register_parser(ClassToConvert, { ..JSON schema.. })
        def _(json_data: ...) -> ClassToConvert:
            ...convert code here...

    If a JSON schema is provided, it will be automatically enforced before the converter code gets to execute (thus, it
    can rely on json_data having a particular type and structure, simplifying the code).

    If `tag` is provided, the parser will be registered under the (class, tag) combination, and that specific combo
    will be required to bring it up.
    """

    def _decorator(f: Callable[[Any], T]):
        PARSER_REGISTRY[(cls, tag)] = RegistryEntry(parser=f, schema=schema)
        return f

    return _decorator


def is_parser_registered(cls: Type, tag: Any = None) -> bool:
    return (cls, tag) in PARSER_REGISTRY


class NoParserRegistered(ValueError):
    def __init__(self, cls: Type, tag: Any):
        super().__init__(
            f"No parser registered for objects of type {cls.__name__}" +
            (f", tag {tag!r}" if tag is not None else "")
        )


class RegistryEntry(NamedTuple):
    parser: Callable[[Any], Any]
    schema: Optional[JSONSchema] = None


PARSER_REGISTRY : Dict[Tuple[Type, Any], RegistryEntry] = dict()
