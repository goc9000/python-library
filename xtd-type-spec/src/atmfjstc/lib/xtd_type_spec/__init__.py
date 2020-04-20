"""
Provides an extended type specification mechanism that offers some extra features vs. just using a <type> object.

Rationale
---------

Normally, in Python, when we want to programmatically specify a type against which a value can be typechecked at
runtime, we can just use a `type` instance and then use ``isinstance(value, type)``. E.g::

    ALLOWED_TYPE = str

    value = 3
    if not isinstance(value, ALLOWED_TYPE):
        raise TypeError("Value type is incorrect")

There are, however, some type specifications that a `type` object cannot represent:

- Union types, i.e. where a value is allowed to be either of a number of types. E.g. ``int | string | float``
- Literal types, where a variable must have a specific value to fit the "type". This is mostly useful when combined
  with the union type, as we can thus limit a value to any of a number of choices, e.g. ``1 | 2 | 3``. This can also
  represent optional types, e.g. ``str | None``

Python's built-in `isinstance` and `issubclass` offer some support for union types, but not for literal types and
combinations thereof. Additionally, `issubclass` only allows a regular (non-union) type on the left side.

Solution
--------

This module provides some utilities for working with an "extended" way of specifying types. Specifically, it offers
the `isinstance_ex` and `issubclass_ex` functions, that mimic the interface of the builtins but support a richer
syntax for expressing types:

- a normal type like `str`, `list` etc. will stand for itself as before
- lists or tuples will be treated as union types, e.g. ``(list, str)`` means ``list | str``
- a hashable, non-class value will be treated as a literal type, e.g. ``(bool, "other")`` will produce a type that
  accepts `True`, `False` or the string ``'other'``
- the tokens `AnyType` and `VoidType` stand for the universal type (any value matches) and null type (no value matches)
  respectively.
- these idioms can be combined recursively, e.g. ``(list, (1, 2, bool))`` although it should be noted that all such
  expressions ultimately reduce to a flat tuple under this simple type system
- one can use an idiom like ``(type, None)`` to represent an optional type

Extras
------

Other features provided in this module:

- `XtdTypeSpec`, a type hint for marking values in your code that are extended type specifications
- `render_xtd_type_spec`, a function for formatting extended type specs in a readable way
- `typecheck`, a convenience function for easily throwing descriptive errors when type checks fail
"""

import typing

from collections.abc import Sequence, Hashable

from atmfjstc.lib.py_lang_utils.token import Token


AnyType = Token(repr_='AnyType')
"""This is used as a token for the universal type (any value matches)."""


VoidType = Token(repr_='VoidType')
"""This is used as a token for the null/void type (no value matches)."""


# This specification is imperfect, might want to revisit it
XtdTypeSpec_Proper = type
XtdTypeSpec_Literal = typing.Hashable
XtdTypeSpec_Union = typing.Sequence['XtdTypeSpec']
XtdTypeSpec_Any = Token
XtdTypeSpec_Void = Token
XtdTypeSpec = typing.Union[
    XtdTypeSpec_Proper, XtdTypeSpec_Literal, XtdTypeSpec_Union, XtdTypeSpec_Any, XtdTypeSpec_Void
]


def isinstance_ex(value: typing.Any, xtd_type_spec: XtdTypeSpec) -> bool:
    """
    Checks whether the given value conforms to the type described by ``xtd_type_spec``.

    See the module description for details on the format of the extended type specification.

    Designed as a drop-in replacement for ``isinstance()``
    """
    if isinstance(xtd_type_spec, type):
        return isinstance(value, xtd_type_spec)
    elif xtd_type_spec == AnyType:
        return True
    elif xtd_type_spec == VoidType:
        return False
    elif _is_proper_sequence(xtd_type_spec):
        return any(isinstance_ex(value, alt) for alt in xtd_type_spec)
    elif isinstance(xtd_type_spec, Hashable):
        return value == xtd_type_spec
    else:
        raise TypeError(f"Invalid extended type specification: {xtd_type_spec!r}")


def issubclass_ex(xtd_type_spec: XtdTypeSpec, parent_type_spec: XtdTypeSpec) -> bool:
    """
    Checks whether the given type is a subtype of another, i.e. all values that would fit ``xtd_type_spec`` will also
    fit ``parent_type_spec``

    See the module description for details on the format of the extended type specification.

    Designed as a drop-in replacement for ``issubclass()``
    """
    if (parent_type_spec == AnyType) or (xtd_type_spec == VoidType):
        return True  # Note that this also covers Any vs Any and Void vs Void (both true)
    if (parent_type_spec == VoidType) or (xtd_type_spec == AnyType):
        return False

    if _is_proper_sequence(xtd_type_spec):
        return all(issubclass_ex(alt, parent_type_spec) for alt in xtd_type_spec)
    if _is_proper_sequence(parent_type_spec):
        return any(issubclass_ex(xtd_type_spec, alt) for alt in parent_type_spec)

    if isinstance(parent_type_spec, type):
        if isinstance(xtd_type_spec, type):
            return issubclass(xtd_type_spec, parent_type_spec)
        elif isinstance(xtd_type_spec, Hashable):
            return isinstance(xtd_type_spec, parent_type_spec)
        else:
            raise TypeError(f"Invalid extended type specification: {xtd_type_spec!r}")

    if isinstance(parent_type_spec, Hashable):
        if isinstance(xtd_type_spec, type):
            return False
        elif isinstance(xtd_type_spec, Hashable):
            return xtd_type_spec == parent_type_spec
        else:
            raise TypeError(f"Invalid extended type specification: {xtd_type_spec!r}")

    raise TypeError(f"Invalid extended type specification: {parent_type_spec!r}")


def _is_proper_sequence(value):
    return isinstance(value, Sequence) and not isinstance(value, str)


def render_xtd_type_spec(xtd_type_spec: XtdTypeSpec, dequalify: bool = False) -> str:
    """
    Returns a more readable representation of an extended type specification.

    By default, type names are de-qualified, i.e. the prefix indicating the specific package they belong to is removed,
    as it decreases readability whereas such conflicts are rare in practice. To keep the type names qualifies, set
    ``dequalify=`` to False.
    """
    if _is_proper_sequence(xtd_type_spec):
        return '(' + (' | '.join(render_xtd_type_spec(alt) for alt in xtd_type_spec)) + ')'
    if xtd_type_spec is AnyType:
        return '<any>'
    if xtd_type_spec is VoidType:
        return '<void>'
    if isinstance(xtd_type_spec, type):
        return ((xtd_type_spec.__module__ + '.') if dequalify and xtd_type_spec.__module__ != 'builtins' else '') + \
            xtd_type_spec.__qualname__

    return repr(xtd_type_spec)


T = typing.TypeVar('T')


def typecheck(value: T, xtd_type_spec: XtdTypeSpec, value_name: str = 'value', dequalify: bool = False) -> T:
    """
    Convenience function that does an ``isinstance_ex`` check and throws a descriptive TypeCheckError if the type does
    not match.

    If the type does match, the function returns the value that was passed, such that one may use this in fluent code
    like::

        dest = typecheck(source, type_spec)
    """
    if isinstance_ex(value, xtd_type_spec):
        return value

    message = f"{value_name} should be {render_xtd_type_spec(xtd_type_spec, dequalify=dequalify)}, " \
        f"is {render_xtd_type_spec(type(value), dequalify=dequalify)}".lstrip()

    raise TypeCheckError(message[0].upper() + message[1:], value, xtd_type_spec)


class TypeCheckError(TypeError):
    offending_value: typing.Any
    expected_type: XtdTypeSpec

    def __init__(self, message: str, offending_value: typing.Any, expected_type: XtdTypeSpec):
        super().__init__(message)
        self.offending_value = offending_value
        self.expected_type = expected_type
