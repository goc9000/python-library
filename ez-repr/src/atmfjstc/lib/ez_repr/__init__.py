"""
Base class that provides a smarter __repr__() function for your objects.

This package provides a base class, `EZRepr`, that automatically provides your objects and their descendants with a
repr() implementation that works reasonably well in most cases, saving you the trouble of the usual boilerplate.

EZRepr's __repr__ implementation will try to automatically figure out the minimal set of fields it should render.
Specifically, it will render all fields that are explicitly initialized in the class body, as long as their current
value is different from the default with which they were initialized. Note that this does not handle defaults provided
in the constructor. For dataclasses, the list of fields will be queried using `dataclasses.fields`, eliminating the
guesswork.

You can tweak various aspects of the rendering (as well as add extra fields) by overriding the `ez_repr_head`,
`ez_repr_fields` etc. methods.

There is also some rudimentary handling of multi-line repr's and tree structures. It's not particularly pretty or
accurate, but miles better than Python's default repr() which does not handle multilines properly at all.
"""

import dataclasses

from inspect import isroutine, isdatadescriptor
from collections import OrderedDict
from textwrap import indent


class EZRepr:
    def __repr__(self):
        return ez_render_object(self._ez_repr_head(), self._ez_repr_fields().items())

    def _ez_repr_head(self):
        return self.__class__.__name__

    def _ez_repr_fields(self):
        data = OrderedDict()

        for field, default_value in self._ez_repr_iter_fields_and_defaults():
            current_value = getattr(self, field)
            try:
                is_diff = (current_value != default_value)
            except Exception:  # A custom __eq__() may throw exceptions, you never know...
                is_diff = True

            if is_diff:
                data[field] = current_value

        return data

    def _ez_repr_iter_fields_and_defaults(self):
        if dataclasses.is_dataclass(self):
            for field in dataclasses.fields(self):
                yield field.name, field.default
        else:
            for parent in reversed(self.__class__.__mro__[:-1]):
                for field, default_value in parent.__dict__.items():
                    if field.startswith('_') or isroutine(default_value) or isdatadescriptor(default_value):
                        continue

                    yield field, default_value


def ez_render_object(name, fields):
    """
    Helper for rendering an arbitrary class instance in the same way as a EZRepr-enabled class, provided you can
    supply the class name and the fields to be rendered.
    """
    head = name + '('
    tail = ')'
    prop_renders = [field + '=' + repr(value) for field, value in fields]

    oneliner = head + ', '.join(prop_renders) + tail
    if (len(oneliner) < 100) and ('\n' not in oneliner):
        return oneliner

    return head + '\n' + ''.join(indent(prop, '  ') + ',\n' for prop in prop_renders) + tail


def as_is(repr_value):
    """
    Takes a string and returns an object whose repr() will resolve to that string. Useful for injecting your own text in
    some other repr().
    """
    return _AsIs(repr_value)


class _AsIs:
    _repr = None

    def __init__(self, repr_vaue):
        self._repr = repr_vaue

    def __repr__(self):
        return self._repr
