"""
Base class that provides a smarter `__repr__` function for your objects.

This package provides a base class, `EZRepr`, that automatically provides your objects and their descendants with a
`repr()` implementation that works reasonably well in most cases, saving you the trouble of typing the usual
boilerplate.

EZRepr's `__repr__` implementation will try to automatically figure out the minimal set of fields it should render.
Specifically, it will render all fields that are explicitly initialized in the class body, as long as their current
value is different from the default with which they were initialized. Note that this does not handle defaults provided
in the constructor. For dataclasses, the list of fields will be queried using `dataclasses.fields`, eliminating the
guesswork.

You can tweak various aspects of the rendering (as well as add extra fields) by overriding the `_ez_repr_head`,
`ez_repr_fields` etc. methods.

The EZRepr renderer also handles nesting and multiline values better than Python's native `repr()`. It will try to
break arrays, dicts and object contents over several lines so as to keep the output within a specified number of
columns. You can use this more advanced renderer in your projects by calling the functions `ez_render_object`,
`ez_render_value` and `as_is`.
"""

import dataclasses
import textwrap

import typing
from typing import Any, Iterable, Tuple, Optional, Mapping, Callable, Union, ItemsView, Sequence

from collections import OrderedDict

from atmfjstc.lib.py_lang_utils.data_objs import get_obj_likely_data_fields_with_defaults


class EZRepr:
    def __repr__(self, **kwargs) -> str:
        """
        For the extra parameters accepted by this generated `repr()` implementation, refer to the `ez_render_object`
        function.
        """
        return ez_render_object(self._ez_repr_head(), self._ez_repr_fields().items(), **kwargs)

    def _ez_repr_head(self) -> str:
        return self.__class__.__name__

    def _ez_repr_fields(self) -> typing.OrderedDict[str, Any]:
        data = OrderedDict()

        for field, default_value in self._ez_repr_iter_fields_and_defaults():
            try:
                current_value = getattr(self, field)
            except Exception:
                continue

            try:
                is_diff = (current_value != default_value)
            except Exception:  # A custom __eq__() may throw exceptions, you never know...
                is_diff = True

            if is_diff:
                data[field] = current_value

        return data

    def _ez_repr_iter_fields_and_defaults(self) -> Iterable[Tuple[str, Any]]:
        if dataclasses.is_dataclass(self):
            for field in dataclasses.fields(self):
                yield field.name, field.default

        yield from get_obj_likely_data_fields_with_defaults(self, include_properties=False).items()


RendererFunc = Union[Callable[[Any], str], Callable[..., str]]
Renderers = Mapping[type, RendererFunc]


def ez_render_object(
    name: str, fields: Union[Iterable[Tuple[str, Any]], ItemsView[str, Any]],
    max_width: Optional[int] = 120, indent: int = 2, renderers: Optional[Renderers] = None
) -> str:
    """
    Helper for rendering an arbitrary class instance in the same way as a `EZRepr`-enabled class, provided you can
    supply the class name and the fields to be rendered.

    Args:
        name: The name rendererd for the object (usually a class name)
        fields: An iterable of (key, value) tuples describing the object's fields. The order of the fields will be
            preserved in the output.
        max_width: If not None, the renderer will try to make the representation fit the given number of columns by
            breaking up properties, lists and dicts over multiple lines if necessary. Otherwise, everything will be
            rendered on a single line as long as no value deep down has a multiline `repr()`.
        indent: How many columns to indent by when rendering the content of a multi-line object, array etc.
        renderers: A mapping from types to renderer functions that controls how values deep inside the object will
            be rendered. Normally `ez_render_value` would be called, but if a type in this dict matches (even as an
            ancestor), the corresponding function will be called instead.

            Note: The renderer function will receive the same parameters as `ez_render_value` (including `max_width`,
            etc) so that it can adapt to the available width in the same way. Naive single-parameter renderers will
            also be accepted.

    Returns:
        The (possibly multiline) string representation of the object.
    """

    fields = list(fields)  # Capture fields (we may only be able to iterate through them once)

    return _render_block(
        name + '(', ')', [value for _, value in fields],
        item_prompts=[field + '=' for field, _ in fields],
        max_width=max_width, indent=indent, renderers=renderers
    )


def ez_render_value(
    value: Any, max_width: Optional[int] = 120, indent: int = 2, renderers: Optional[Renderers] = None
) -> str:
    """
    Renders an arbitrary value using EZRepr's advanced renderer.

    - For native Python dicts, lists and tuples (but not their subclasses!), this renders them in a nice way that
      breaks them over multiple lines in order to fit the maximum width or accommodate multi-line values
    - For EZRepr-enabled values, this ensures that the user-supplied indent, etc. params are passed to the underlying
      renderer (it may seem useless to call `ez_render_value` directly just for that, but note that `ez_render_value` is
      called automatically for each value in a list etc.)
    - Other values will just be rendered using `repr()`.

    The `max_width`, `indent` and `renderers` parameters are the same as for `ez_render_object`.
    """
    if renderers is not None:
        for cls in value.__class__.__mro__:
            if cls in renderers:
                renderer = renderers[cls]

                try:
                    # Try full featured renderer first
                    return renderer(value, max_width=max_width, indent=indent, renderers=renderers)
                except Exception:
                    pass

                # Fall back to a naive renderer interface
                return renderer(value)

    if type(value) == tuple:
        return _render_block('(', ')', value, max_width=max_width, indent=indent, tuple_mode=True, renderers=renderers)
    if type(value) == list:
        return _render_block('[', ']', value, max_width=max_width, indent=indent, renderers=renderers)
    if type(value) == dict:
        items = value.items()
        return _render_block(
            '{', '}', [v for _, v in items],
            item_prompts=[repr(k) + ': ' for k, _ in items], max_width=max_width, indent=indent, renderers=renderers
        )

    if isinstance(value, EZRepr):
        try:
            # Note: this will only work if the user did not override the repr() supplied by EZRepr
            return value.__repr__(max_width=max_width, indent=indent, renderers=renderers)
        except Exception:
            pass

        # Fall back to the usual repr()
        return repr(value)

    return repr(value)


def _render_block(
    head: str, tail: str, items: Sequence[Any], max_width: Optional[int], indent: int,
    item_prompts: Sequence[str] = None, tuple_mode: bool = False, renderers: Optional[Renderers] = None
) -> str:
    if item_prompts is None:
        item_prompts = [''] * len(items)

    last_comma = ',' if (tuple_mode and (len(items) == 1)) else ''
    item_tails = ([','] * (len(items) - 1) + [last_comma]) if len(items) > 0 else []

    item_oneline_renders = [
        item_head + ez_render_value(item, max_width=None, renderers=renderers) + item_tail
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
                item_head + ez_render_value(item, max_width=new_width, indent=indent, renderers=renderers) + item_tail,
                ' ' * indent,
            ))

    out_parts.append(tail)

    return '\n'.join(out_parts)


def _test_oneliner(candidate: str, max_width: Optional[int]) -> bool:
    return ('\n' not in candidate) and ((max_width is None) or (len(candidate) <= max_width))


def as_is(repr_value: str) -> '_AsIs':
    """
    Takes a string and returns an object whose repr() will resolve to that string. Useful for injecting your own text in
    some other repr().
    """
    return _AsIs(repr_value)


class _AsIs:
    _repr = None

    def __init__(self, repr_value: str):
        self._repr = repr_value

    def __repr__(self) -> str:
        return self._repr
