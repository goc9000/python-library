"""
Provides an extended type specification mechanism that offers some extra features vs. just using a <type> object.

Rationale
---------

Normally, in Python, when we want to programmatically specify a type against which a value can be typechecked at
runtime, we can just use a <type> instance and then use ``isinstance(value, type)``. E.g::

    ALLOWED_TYPE = str

    value = 3
    if not isinstance(value, ALLOWED_TYPE):
        raise TypeError("Value type is incorrect")

There are, however, some type specifications that a <type> object cannot represent:

- Union types, i.e. where a value is allowed to be either of a number of types. E.g. "int | string | float"
- Constant types, where a variable must have a specific value to fit the "type". This is mostly useful when combined
  with the union type, as we can thus limit a value to any of a number of choices, e.g. "1 | 2 | 3". This can also
  represent optional types, e.g. "str | None"

Python's built-in ``isinstance`` and ``issubclass`` offer some support for union types, but not for constant types and
combinations thereof. Additionally, ``issubclass`` only allows a regular (non-union) type on the left side.

Solution
--------

This module provides some utilities for working with an "extended" way of specifying types. Specifically, it offers
the ``isinstance_ex`` and ``issubclass_ex`` functions, that mimic the interface of the builtins but support a richer
syntax for expressing types:

- a normal type like ``str``, ``list`` etc. will stand for itself as before
- lists or tuples will be treated as union types, e.g. ``(list, str)`` means list|str
- a hashable, non-class value will be treated as a constant type, e.g. ``(bool, "other")`` will produce a type that
  accepts ``True``, ``False`` or the string ``'other'``
- the tokens ``AnyType`` and ``VoidType`` stand for the universal type (any value matches) and null type (no
  value matches) respectively.
- these idioms can be combined recursively, e.g. ``(list, (1, 2, bool))`` although it should be noted that all such
  expressions ultimately reduce to a flat tuple under this simple type system
- one can use an idiom like ``(type, None)`` to represent an optional type

Extras
------

Other features provided in this module:

- ``XtdTypeSpec``, a type hint for marking values in your code that are extended type specifications
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
XtdTypeSpec_Const = typing.Hashable
XtdTypeSpec_Union = typing.Sequence['XtdTypeSpec']
XtdTypeSpec_Any = Token
XtdTypeSpec_Void = Token
XtdTypeSpec = typing.Union[XtdTypeSpec_Proper, XtdTypeSpec_Const, XtdTypeSpec_Union, XtdTypeSpec_Any, XtdTypeSpec_Void]


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
    elif _is_sequence(xtd_type_spec):
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

    if _is_sequence(xtd_type_spec):
        return all(issubclass_ex(alt, parent_type_spec) for alt in xtd_type_spec)
    if _is_sequence(parent_type_spec):
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


def _is_sequence(value):
    return isinstance(value, Sequence) and not isinstance(value, str)
