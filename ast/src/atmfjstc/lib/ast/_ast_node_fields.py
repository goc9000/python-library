from typing import Any, Callable, Tuple, Optional
from collections.abc import Iterable
from dataclasses import dataclass, field

from atmfjstc.lib.ez_repr import EZRepr
from atmfjstc.lib.xtd_type_spec import typecheck, issubclass_ex, AnyType, XtdTypeSpec

from atmfjstc.lib.ast._initialization import NVP


@dataclass(frozen=True, repr=False)
class ASTNodeFieldDefBase(EZRepr):
    """
    This represents the definition of a field in an AST node.

    There are three kinds of fields:

    - Child: A slot containing a single child (another AST node). May be None if options permit.
    - Child List: A list of children (AST nodes)
    - Param: Any other kind of parameter that is not an AST node

    Attributes:
        name: The name of the field
        allowed_type: Restricts the type of value/node that can go into the field. Must be an extended type
            specification (see the ``xtd_type_spec`` package for details).

            Notes:

            - In addition to this restriction, items in a child/child-list field must also be AST nodes.
            - For a child list field, the `type` check (and any other check) is applied to each child, not to the
              iterable of children itself.

        allow_none: Allows params or single child slots to accept the value None (which is normally not the case).

            This field is always locked to False for child list fields.

        checks: A tuple of functions that are called on an incoming value to ensure that it meets semantic checks (e.g.
            strings that should be non-empty or match some regex). If a check fails, the function should either return
            False or throw an exception, preferably a `TypeError` or `ValueError`.

            Notes:

            - The functions are called in order, after the value has passed the type check
            - The value None, if allowed, is NOT checked

        coerce: A function that is called on an incoming value before any other checks are made, so as to try to
            convert it to the accepted type if it is compatible (e.g. allowing lists for a parameter that accepts only
            tuples). Should be used sparingly.

            Note that unlike the other checks, the coerce function can be called with a None value if one is supplied.

        default: Specifies a default value for this field.

            Note: no checks are performed for the default value. It must be of the same type that would pass the node's
            `type` check.

        kw_only: Specifies that this field can only be initialized using keyword parameter syntax (as opposed to
            positional)
    """

    name: str

    kw_only: bool = False
    allow_none: bool = False
    coerce: Optional[Callable[[Any], Any]] = None
    allowed_type: XtdTypeSpec = AnyType
    checks: Tuple[Callable[[Any], Optional[bool]], ...] = ()
    default: Any = NVP

    def __post_init__(self):
        if len(self.name) == 0:
            raise ValueError("Field name must be non-empty!")

    def prepare_field_value(self, value):
        """
        Checks and adjusts a user-supplied value in accordance to the type and options of this field.

        Specifically:

        - Defaults are applied (if the value is NVP)
        - The value is coerced if necessary (e.g. child lists become tuples)
        - The type of the value is checked

        Returns the adjusted value or throws an exception.
        """
        if value == NVP:
            return self.default

        if value == NVP:
            raise ValueError(f"No value provided and no default for field '{self.name}'")

        try:
            value = self._coerce_incoming_value(value)
            self._check_value(value)
        except Exception as e:
            raise TypeError(f"Invalid value provided for field '{self.name}'") from e

        return value

    def _coerce_incoming_value(self, value):
        return value   # Do nothing by default

    def _check_value(self, value):
        if self.coerce is not None:
            value = self.coerce(value)

        if value is None:
            if self.allow_none:
                return

            raise TypeError("May not be None")

        self._final_typecheck(value)

        for checker in self.checks:
            if checker(value) is False:
                raise ValueError(f"Failed check '{checker.__name__}'")

    def _final_typecheck(self, value):
        typecheck(value, self.allowed_type)

    def override(self, new_field):
        """
        Returns a field definition that is the result of overriding this definition with one in a subclass.

        The function mainly does sanity checks to ensure the overriding makes sense. The actual result should be
        mostly identical to the new field definition.
        """

        try:
            assert self.__class__ == new_field.__class__, "Kind should be the same"
            assert self.name == new_field.name, "Name should be the same"
            assert self.kw_only == new_field.kw_only, "kw_only option should be the same"

            if new_field.allow_none and not self.allow_none:
                raise TypeError("Cannot allow None values if overridden field does not allow them (would broaden type)")
            if not issubclass_ex(new_field.allowed_type, self.allowed_type):
                raise TypeError("New field type is not a subtype of the old field type")

            return self.__class__(
                self.name,
                kw_only=self.kw_only,
                allow_none=new_field.allow_none,
                allowed_type=new_field.allowed_type,
                default=new_field.default,
            )
        except Exception as e:
            raise TypeError(f"Cannot override AST node field {self} with {new_field}") from e


@dataclass(frozen=True, repr=False)
class ASTNodeChildFieldDefBase(ASTNodeFieldDefBase):
    def _final_typecheck(self, value):
        from atmfjstc.lib.ast import ASTNode

        typecheck(value, ASTNode, value_name='child')
        super()._final_typecheck(value)


@dataclass(frozen=True, repr=False)
class ASTNodeChildFieldDef(ASTNodeChildFieldDefBase):
    pass


@dataclass(frozen=True, repr=False)
class ASTNodeChildListFieldDef(ASTNodeChildFieldDefBase):
    allow_none: bool = field(init=False, default=False)

    def _coerce_incoming_value(self, value):
        if not isinstance(value, Iterable):
            raise TypeError("Must provide an iterable (list, tuple, stream etc)")

        return tuple(value)

    def _check_value(self, value):
        for child_index, child in enumerate(value):
            try:
                super()._check_value(child)
            except Exception as e:
                raise TypeError(f"Error for child #{child_index}") from e


@dataclass(frozen=True, repr=False)
class ASTNodeParamFieldDef(ASTNodeFieldDefBase):
    pass


def parse_ast_node_field(field_spec):
    try:
        if not isinstance(field_spec, tuple) or len(field_spec) not in [2,3]:
            raise TypeError("Field spec must be a tuple of length 2 or 3")

        kind, name, options = (field_spec + (dict(),))[:3]

        cls = {
            'CHILD': ASTNodeChildFieldDef,
            'CHILD_LIST': ASTNodeChildListFieldDef,
            'PARAM': ASTNodeParamFieldDef,
        }.get(kind)

        if cls is None:
            raise TypeError("Field kind must be CHILD, CHILD_LIST or PARAM")

        init_params = dict()
        for key, value in options.items():
            if key == 'check':
                key = 'checks'
            if key == 'type':
                key = 'allowed_type'

            if key == 'checks':
                value = tuple(value) if isinstance(value, Iterable) else (value,)

            init_params[key] = value

        return cls(name, **init_params)
    except Exception as e:
        raise TypeError(f"Error parsing AST node field specification '{field_spec!r}'") from e
