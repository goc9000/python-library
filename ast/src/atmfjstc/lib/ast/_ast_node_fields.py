from typing import Any
from collections.abc import Iterable
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass

from atmfjstc.lib.ez_repr import EZRepr
from atmfjstc.lib.xtd_type_spec import typecheck, issubclass_ex, AnyType, XtdTypeSpec

from atmfjstc.lib.ast._initialization import NVP


@dataclass(frozen=True, repr=False)
class ASTNodeFieldDefBase(EZRepr, metaclass=ABCMeta):
    """
    This represents the definition of a field in an AST node.

    There are three kinds of fields:

    - Child: A slot containing a single child (another AST node). May be None if options permit.
    - Child List: A list of children (AST nodes)
    - Param: Any other kind of parameter that is not an AST node

    Each field can be configured with a number of options, as follows:

    - ``type``: Restricts the type of value/node that can go into the field. Must be an extended type specification (see
                the ``xtd_type_spec`` package for details). Note that in addition to this restriction, items in a
                child/child-list field must also be AST nodes.
    - ``allow_none``: Allows params or single child slots to accept the value None (which is normally not the case).
    - ``default``: Specifies a default value for this field
    - ``kw_only``: Specifies that this field can only be initialized using keyword parameter syntax (as opposed to
                   positional)
    """

    name: str

    kw_only: bool = False
    allow_none: bool = False
    allowed_type: XtdTypeSpec = AnyType
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
            value = self.default

        if value == NVP:
            raise ValueError(f"No value provided and no default for field '{self.name}'")

        try:
            self._pre_coerce_type_check_value(value)
            self._type_check_value(self._coerce_incoming_value(value))
        except Exception as e:
            raise TypeError(f"Invalid value provided for field '{self.name}'") from e

        return value

    def _pre_coerce_type_check_value(self, value):
        pass  # Do nothing by default

    def _coerce_incoming_value(self, value):
        return value   # Do nothing by default

    @abstractmethod
    def _type_check_value(self, value):
        pass

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
class ASTNodeChildFieldDef(ASTNodeFieldDefBase):
    def _type_check_value(self, value):
        from atmfjstc.lib.ast import ASTNode

        if value is None:
            if self.allow_none:
                return

            raise TypeError("May not be None")

        typecheck(value, ASTNode, value_name='child')
        self._final_typecheck(value)


@dataclass(frozen=True, repr=False)
class ASTNodeChildListFieldDef(ASTNodeFieldDefBase):
    def _pre_coerce_type_check_value(self, value):
        if not isinstance(value, Iterable):
            raise TypeError("Must provide an iterable (list, tuple, stream etc)")

    def _coerce_incoming_value(self, value):
        return tuple(value)

    def _type_check_value(self, value):
        from atmfjstc.lib.ast import ASTNode

        for child_index, child in enumerate(value):
            try:
                if child is None:
                    raise TypeError("May not be None")

                typecheck(child, ASTNode, value_name='child')
                self._final_typecheck(child)
            except Exception as e:
                raise TypeError(f"Error for child #{child_index}") from e


@dataclass(frozen=True, repr=False)
class ASTNodeParamFieldDef(ASTNodeFieldDefBase):
    def _type_check_value(self, value):
        if value is None:
            if self.allow_none:
                return

            raise TypeError("May not be None")

        self._final_typecheck(value)


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

        def _adjust_name(key):
            return 'allowed_type' if key == 'type' else key

        init_params = {_adjust_name(key): value for key, value in options.items()}

        return cls(name, **init_params)
    except Exception as e:
        raise TypeError(f"Error parsing AST node field specification '{field_spec!r}'") from e
