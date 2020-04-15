"""
Base class that provides a smarter __repr__() function for your objects.

This package provides a base class, ``EZRepr``, that automatically provides your objects and their descendants with a
``repr()`` implementation that works reasonably well in most cases, saving you the trouble of the usual boilerplate.

EZRepr's ``__repr__`` implementation will try to automatically figure out the minimal set of fields it should render.
Specifically, it will render all fields that are explicitly initialized in the class body, as long as their current
value is different from the default with which they were initialized. Note that this does not handle defaults provided
in the constructor. For dataclasses, the list of fields will be queried using `dataclasses.fields`, eliminating the
guesswork.

You can tweak various aspects of the rendering (as well as add extra fields) by overriding the ``_ez_repr_head``,
``ez_repr_fields`` etc. methods.

There is also some rudimentary handling of multi-line repr's and tree structures. It's not particularly pretty or
accurate, but miles better than Python's default repr() which does not handle multilines properly at all.
"""

import dataclasses
import textwrap

from inspect import isroutine, isdatadescriptor
from collections import OrderedDict


class EZRepr:
    def __repr__(self, **kwargs):
        """
        For the extra parameters accepted by this generated repr(), refer to the ``ez_render_object`` function.
        """
        return ez_render_object(self._ez_repr_head(), self._ez_repr_fields().items(), **kwargs)

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


def ez_render_object(name, fields, max_width=120, indent=2):
    """
    Helper for rendering an arbitrary class instance in the same way as a EZRepr-enabled class, provided you can
    supply the class name and the fields to be rendered.

    The rendering is further controlled by these parameters:

    - `max_width`: Tries to render items so as to fit a given number of columns (breaking up properties, lists and
      dicts over multiple lines if necessary). If this is set to None, everything will be rendered on a single line
      as long as no value deep down has a multiline repr().
    - `indent`: How many columns to indent by when rendering the content of a multi-line object, array etc
    """
    return _render_block(
        name + '(', ')', [value for _, value in fields],
        item_prompts=[field + '=' for field, _ in fields],
        max_width=max_width, indent=indent
    )


def ez_render_value(value, max_width=120, indent=2):
    """
    Renders an arbitrary value using EZRepr's advanced renderer.

    - For native Python dicts, lists and tuples (but not their subclasses!), this renders them in a nice way that
      breaks them over multiple lines in order to fit the maximum width or accomodate multi-line values
    - For EZRepr-enabled values, this ensures that the user-supplied indent, etc. params are passed to the underlying
      renderer (it may seem useless to call ez_render_value directly just for that, but note that ez_render_value is
      called automatically for each value in a list etc.)
    - Other values will just be rendered using repr().
    """
    if type(value) == tuple:
        return _render_block('(', ')', value, max_width=max_width, indent=indent, tuple_mode=True)
    if type(value) == list:
        return _render_block('[', ']', value, max_width=max_width, indent=indent)
    if type(value) == dict:
        items = value.items()
        return _render_block(
            '{', '}', [v for _, v in items],
            item_prompts=[repr(k) + ': ' for k, _ in items], max_width=max_width, indent=indent
        )

    if isinstance(value, EZRepr):
        try:
            # Note: this will only work if the user did not override the repr() supplied by EZRepr
            return value.__repr__(max_width=max_width, indent=indent)
        except Exception:
            pass

        # Fall back to the usual repr()
        return repr(value)

    return repr(value)


def _render_block(head, tail, items, max_width, indent, item_prompts=None, tuple_mode=False):
    if item_prompts is None:
        item_prompts = [''] * len(items)

    last_comma = ',' if (tuple_mode and (len(items) == 1)) else ''
    item_tails = ([','] * (len(items) - 1) + [last_comma]) if len(items) > 0 else []

    item_oneline_renders = [
        item_head + ez_render_value(item, max_width=None) + item_tail
        for item_head, item, item_tail in zip(item_prompts, items, item_tails)
    ]

    oneliner = head + ' '.join(item_oneline_renders) + tail
    if ((max_width is None) or (len(oneliner) < max_width)) and ('\n' not in oneliner):
        return oneliner

    # Try multiline render

    new_width = (max_width - indent) if max_width is not None else None

    out_parts = [head]

    for item_head, item, item_tail, oneline_render in zip(item_prompts, items, item_tails, item_oneline_renders):
        if _test_oneliner(oneline_render, new_width):
            out_parts.append(' ' * indent + oneline_render)
        else:
            out_parts.append(textwrap.indent(
                item_head + ez_render_value(item, max_width=new_width, indent=indent) + item_tail,
                ' ' * indent,
            ))

    out_parts.append(tail)

    return '\n'.join(out_parts)


def _test_oneliner(candidate, max_width):
    return ('\n' not in candidate) and ((max_width is None) or (len(candidate) <= max_width))


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
