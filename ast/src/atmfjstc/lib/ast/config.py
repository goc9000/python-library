from typing import Any, Callable, Tuple, Optional, Union, Dict
from collections.abc import Iterable
from dataclasses import dataclass, field

from atmfjstc.lib.ez_repr import EZRepr
from atmfjstc.lib.xtd_type_spec import typecheck, issubclass_ex, AnyType, XtdTypeSpec

from atmfjstc.lib.ast._initialization import NVP


ASTNodeRawFieldSpec = Union[Tuple[str, str], Tuple[str, str, Dict]]
ASTNodeRawConfigItem = Union[str, ASTNodeRawFieldSpec]
ASTNodeRawConfig = Tuple[ASTNodeRawConfigItem, ...]


@dataclass(frozen=True, repr=False)
class ASTNodeFieldSpec(EZRepr):
    """
    This represents the definition of a field in an AST node.

    There are three kinds of fields:

    - Child: A slot containing a single child (another AST node). May be None if options permit.
    - Child List: A list of children (AST nodes)
    - Param: Any other kind of parameter that is not an AST node

    For an explanation of the attributes here, consult the package documentation.
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

    def override(self, new_field: 'ASTNodeFieldSpec') -> 'ASTNodeFieldSpec':
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

            init_data = dict(
                name=self.name,
                kw_only=self.kw_only,
                coerce=new_field.coerce or self.coerce,
                allowed_type=new_field.allowed_type,
                checks=self.checks + new_field.checks,
                default=new_field.default,
            )

            if not isinstance(self, ASTNodeChildListFieldSpec):
                init_data['allow_none'] = new_field.allow_none

            return self.__class__(**init_data)
        except Exception as e:
            raise TypeError(f"Cannot override AST node field {self} with {new_field}") from e

    @staticmethod
    def parse(raw_field_spec: ASTNodeRawFieldSpec) -> 'ASTNodeFieldSpec':
        try:
            if not isinstance(raw_field_spec, tuple) or len(raw_field_spec) not in [2, 3]:
                raise TypeError("Field spec must be a tuple of length 2 or 3")

            kind, name, options = (raw_field_spec + (dict(),))[:3]

            cls = {
                'CHILD': ASTNodeSingleChildFieldSpec,
                'CHILD_LIST': ASTNodeChildListFieldSpec,
                'PARAM': ASTNodeParamFieldSpec,
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
            raise TypeError(f"Error parsing AST node field specification '{raw_field_spec!r}'") from e


@dataclass(frozen=True, repr=False)
class ASTNodeChildFieldSpecBase(ASTNodeFieldSpec):
    def _final_typecheck(self, value):
        from atmfjstc.lib.ast import ASTNode

        typecheck(value, ASTNode, value_name='child')
        super()._final_typecheck(value)


@dataclass(frozen=True, repr=False)
class ASTNodeSingleChildFieldSpec(ASTNodeChildFieldSpecBase):
    pass


@dataclass(frozen=True, repr=False)
class ASTNodeChildListFieldSpec(ASTNodeChildFieldSpecBase):
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
class ASTNodeParamFieldSpec(ASTNodeFieldSpec):
    pass


@dataclass(frozen=True, repr=False)
class ASTNodeConfig(EZRepr):
    """
    This is a class for storing the configuration for an AST node (its set of fields and whether it is abstract)
    """

    is_abstract: bool
    fields: Tuple[ASTNodeFieldSpec, ...]

    def extend(self, child_config: 'ASTNodeConfig') -> 'ASTNodeConfig':
        """
        Adds the fields and configuration of another config to this one and returns the result.

        Fields in the child config will override those in the parent having the same name.
        """
        field_indexes = {field.name: index for index, field in enumerate(self.fields)}
        new_fields = list(self.fields)

        for field in child_config.fields:
            old_field_index = field_indexes.get(field.name)
            if old_field_index is not None:
                new_fields[old_field_index] = new_fields[old_field_index].override(field)
            else:
                new_fields.append(field)

        return ASTNodeConfig(
            is_abstract=child_config.is_abstract,
            fields=tuple(new_fields),
        )

    @staticmethod
    def parse(raw_config: ASTNodeRawConfig) -> 'ASTNodeConfig':
        is_abstract = False
        fields = []
        names_seen = set()

        for item in raw_config:
            if item == 'abstract':
                is_abstract = True
            else:
                field = ASTNodeFieldSpec.parse(item)

                if field.name in names_seen:
                    raise AssertionError(f"Duplicate field '{field.name}' in AST node config")

                fields.append(field)
                names_seen.add(field.name)

        return ASTNodeConfig(
            is_abstract=is_abstract,
            fields=tuple(fields),
        )
