"""
Provides a mechanism for building Abstract Syntax Trees (ASTs) useful for representing typed tree data, such as that
resulting from a parsing operation.

It's easiest to start with an example::

    class Expression(ASTNode):
        AST_NODE_CONFIG = ('abstract',)

    class Term(Expression):
        AST_NODE_CONFIG = (
            ('PARAM', 'value', dict(type=int)),
        )

    class Operator(Expression):
        AST_NODE_CONFIG = (
            ('PARAM', 'op', dict(type=('+', '-', '*', '/'))),
            ('CHILD', 'left_side', dict(type=Expression)),
            ('CHILD', 'right_side', dict(type=Expression)),
        )


    # This is how we represent 1+2*3

    ex = Operator('+', left_side=Term(1), right_side=Operator('*', Term(2), Term(3)))

    # Find all additions

    for node in ex.iter_subtree(only_type=Operator):
        if node.op == '+':
            print("Addition between {} and {}".format(node.left_side, node.right_side))

Features provided by this system
--------------------------------

- Nodes act like strictly typed structures. Only the fields defined in the ``AST_NODE_CONFIG`` can be set, and only
  with values respecting the defined types.
- Nodes are immutable, allowing trees and parts thereof to be easily passed as if they were value types. To change an
  AST node, use the ``.alter`` function to provide a modified copy (similar to how ``._replace()`` is used in named
  tuples).
- Node fields have the full set of features typical of function parameters: positional vs. keyword specification,
  default values etc.
- Nodes differentiate between fields that define a node's identity (PARAMs) versus those that act as slots for child
  nodes and thus define the tree structure (CHILD and CHILD_LIST fields)
- Each node comes with a set of methods for iterating and modifying the whole subtree
- Inheritance is supported (and recommended)
- Nodes (and thus subtrees) are hashable and can be tested for equality

Usage and Reference
-------------------

It is best to start with creating a base node type that will identify all nodes in your particular application::

    class MyNode(ASTNode):
        AST_NODE_CONFIG = ('abstract',)

All other node types for this kind of tree will derive from ``MyNode`` and define their own fields etc.

Each node class should have an ``AST_NODE_CONFIG`` tuple that defines the node's *specific* fields (i.e. other than
those inherited from a parent) and whether it is abstract or not. To wit, each item in the ``AST_NODE_CONFIG`` can be
either:

- The string ``'abstract'``: Marks this node type as abstract. It cannot be instantiated by itself but can only serve
  as a base for other node types.

  - Note: Abstract nodes *can* have fields.
  - Note: Abstract status is not inherited. Derived classes must be explicitly marked abstract too if needed.

- A tuple like ``('KIND', 'name', dict(option1=..., option2=...)``: A field definition, where:

  - ``'KIND'`` defines the field type. It can be:

    - ``'CHILD'``: A slot for containing a single child (another AST node).
    - ``'CHILD_LIST'``: A list of children (AST nodes)
    - ``'PARAM'``: Any other kind of parameter that is not an AST node

  - ``'name'`` is the field name
  - ``dict(..)`` specifies extra options for the field (can be absent if there are none):

    - ``type``: Restricts the type of value/node that can go into the field. Must be an extended type specification
      (see the ``xtd_type_spec`` package for details). Note that in addition to this restriction, items in a child/
      child-list field must also be AST nodes.
    - ``allow_none``: Allows params or single child slots to accept the value ``None`` (which is normally not the case).
    - ``default``: Specifies a default value for this field
    - ``kw_only``: Specifies that this field can only be initialized using keyword parameter syntax (as opposed to
      positional)
"""

from atmfjstc.lib.py_lang_utils.searching import index_where
from atmfjstc.lib.ast._ast_node_fields import parse_ast_node_field, ASTNodeChildFieldDef, ASTNodeChildListFieldDef
from atmfjstc.lib.ast._initialization import parse_ast_node_args


class ASTNode:
    """
    Base class for building AST (Abstract Syntax Tree) nodes. See package doc for usage.
    """
    AST_NODE_CONFIG = ('abstract',)

    _ast_data = None

    def __init__(self, *args, **kwargs):
        try:
            self._ast_data = dict()

            if self.is_abstract_node_type():
                raise TypeError("Node type is abstract")

            self._ast_data = parse_ast_node_args(self.field_defs(), args, kwargs)

            self._sanity_check_post_init()
        except Exception as e:
            raise ValueError("Error instantiating {}".format(self.__class__.__name__)) from e

    def _sanity_check_post_init(self):
        """
        This method can be overridden in specific node types to provide semantic sanity checking upon node creation.

        Throw exceptions here as needed.
        """
        pass   # Do nothing by default

    @classmethod
    def ast_node_config(cls):
        """
        Returns the complete set of fields and abstract status in effect for this node type. Fields are presented in
        reverse MRO order (i.e. from ASTNode through all the ancestors up to the current node type).
        """

        # Note: we are using .__dict__.get() to ensure that we only get the value for this class, not inherit it from
        # its parent.
        cached = cls.__dict__.get('_cached_ast_node_config')
        if cached is not None:
            return cached

        is_abstract = False
        field_defs = []

        for parent in reversed(cls.__mro__[:-1]):
            is_abstract = False

            node_config = parent.__dict__.get('AST_NODE_CONFIG')
            if node_config is None:
                continue

            for item in node_config:
                if item == 'abstract':
                    is_abstract = True
                else:
                    field_def = parse_ast_node_field(item)

                    old_field_index = index_where(field_defs, lambda f: f.name == field_def.name)
                    if old_field_index is not None:
                        old_field = field_defs.pop(old_field_index)
                        field_def = old_field.override(field_def)

                    field_defs.append(field_def)

        result = dict(
            is_abstract=is_abstract,
            field_defs=field_defs,
        )

        cls._cached_ast_node_config = result

        return result

    @classmethod
    def is_abstract_node_type(cls):
        """
        Returns True if this is an abstract node type (i.e. only meant to serve as an ancestor for concrete nodes)
        """
        return cls.ast_node_config()['is_abstract']

    @classmethod
    def field_defs(cls):
        """
        A list of field definitions applicable to this AST node class, in reverse MRO order (ancestor -> child)
        """
        return cls.ast_node_config()['field_defs']

    def all_field_values(self):
        """
        A list of (field_definition, field_value) pairs, presented in reverse MRO order.
        """
        return [(field, self._ast_data[field.name]) for field in self.field_defs()]

    def __getattr__(self, name):
        if name in self._ast_data:
            return self._ast_data[name]

        raise AttributeError("Attribute '{}' not found in AST node of type {}".format(name, self.__class__.__name__))

    def __setattr__(self, name, value):
        if name == '_ast_data':
            super().__setattr__(name, value)
        else:
            raise AttributeError("Attribute '{}' cannot be set in immutable AST Node. Use alter()".format(name))

    def __deepcopy__(self, memodict):
        return self

    def __repr__(self):
        from atmfjstc.lib.ast._render_repr import render_ast_node_repr

        return render_ast_node_repr(self)

    def __eq__(self, other):
        if not isinstance(other, ASTNode):
            return False
        if other.__class__ != self.__class__:
            return False

        return self._ast_data == other._ast_data

    def __hash__(self):
        hashable_data = [self.__class__.__name__]

        for field, value in self.all_field_values():
            hashable_data.append(field.name)
            hashable_data.append(_compute_hash(value))

        return hash(tuple(hashable_data))

    def alter(self, **kwargs):
        """
        Returns a copy of this node/subtree with the specified fields modified.
        """
        values = dict(self._ast_data)
        values.update(**kwargs)

        return self.__class__(**values)

    def iter_subtree(self, only_type=None, root_first=True, include_root=True):
        """
        Iterates through this node and all of its children, and all of their children etc.
        """
        if root_first:
            if include_root:
                if only_type is None or isinstance(self, only_type):
                    yield self

        for child in self.iter_children():
            for item in child.iter_subtree(root_first=root_first, only_type=only_type):
                yield item

        if not root_first:
            if include_root:
                if only_type is None or isinstance(self, only_type):
                    yield self

    def iter_children(self):
        """
        Iterates through this node's children (and them alone), if any exist.
        """
        for field, value in self.all_field_values():
            if isinstance(field, ASTNodeChildFieldDef):
                if value is not None:
                    yield value
            elif isinstance(field, ASTNodeChildListFieldDef):
                yield from value

    def replace_subtree(self, callback, only_type=None, root_first=True):
        """
        Recursively replaces data throughout this node and its children, their children etc. and returns the modified
        subtree (the original is of course unaffected, as per the immutable nature of ASTs).

        The ``callback`` will receive each node as it is visited. It must return an altered copy of the node (or
        the unchanged node if so desired). It can also return ``None`` which means the visited node should be deleted.

        Note that the callback can modify the child lists themselves, but should not recurse into children (rather,
        leave that to this function).
        """
        cb = callback
        if only_type is not None:
            callback = lambda node: cb(node) if isinstance(node, only_type) else node

        root_replacement = callback(self) if root_first else self

        if root_replacement is None:
            return None

        replacements = dict()

        # Note that we use the replacement node's config, not our own, because the node type may have changed
        for field, value in root_replacement.all_field_values():
            if isinstance(field, ASTNodeChildFieldDef):
                if value is not None:
                    replacements[field.name] = value.replace_subtree(callback, root_first=root_first)
            elif isinstance(field, ASTNodeChildListFieldDef):
                replacements[field.name] = tuple(
                    replacement
                    for replacement in (
                        item.replace_subtree(callback, root_first=root_first)
                        for item in value
                    )
                    if replacement is not None
                )

        root_replacement = root_replacement.alter(**replacements)

        return root_replacement if root_first else callback(root_replacement)


def _compute_hash(value):
    if isinstance(value, (list, tuple)):
        return hash(tuple(_compute_hash(item) for item in value))

    if isinstance(value, dict):
        hashable_data = []
        for key in sorted(value.keys()):
            hashable_data.append(key)
            hashable_data.append(_compute_hash(value[key]))

        return hash(tuple(hashable_data))

    return hash(value)
