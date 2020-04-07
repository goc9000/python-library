from atmfjstc.lib.py_lang_utils.searching import last_index_where

from atmfjstc.lib.abstract_codegen.ast.base import AbstractCodegenASTNode, PromptableNode


class Sequence(AbstractCodegenASTNode):
    """
    A vertical sequence of sections that are rendered one after the other.

    A system is also provided by which one can set margins for the rendered sections. `Sequence` will then insert blank
    lines between the sections so as to satisfy their margin requirements, i.e. an item that has a top margin of *M*
    will have at least *M* blank lines between itself and the preceding item, while its bottom margin setting will
    control the minimum number of blank lines between it and the next item. Margins overlap, such that when an item's
    bottom margin meets the next item's top margin, the greater of these two applies.

    Margins can be automatically set for all items using the `items_margin` property. To set margins for an individual
    item, wrap it in a `Section` node.

    Notes:

    - This is the main workhorse that is generally used to organize the top-level content of a file, or the code inside
      methods, procedures etc.
    - Margins do not apply between an item and the top/bottom of the Sequence itself.
    - Margins are ignored for an item that is empty (produces no lines)
    """
    AST_NODE_CONFIG = (
        ('CHILD_LIST', 'content', dict(type=AbstractCodegenASTNode)),
        ('PARAM', 'items_margin', dict(type=int, default=0)),
    )

    def render(self, context):
        filtered_sections = []

        for section in self.content:
            rendering = list(section.render(context))
            if len(rendering) == 0:
                continue

            margin_top, margin_bottom = \
                section.effective_margins if isinstance(section, Section) else (self.items_margin, self.items_margin)

            filtered_sections.append((rendering, margin_top, margin_bottom))

        prev_margin = None
        for rendering, margin_top, margin_bottom in filtered_sections:
            if prev_margin is not None:
                for _ in range(max(prev_margin, margin_top)):
                    yield ''

            yield from rendering

            prev_margin = margin_bottom


class Section(AbstractCodegenASTNode):
    """
    Wraps another node and allows exposing margin top/bottom properties that apply only to this node in a `Sequence`.
    """
    AST_NODE_CONFIG = (
        ('CHILD', 'content', dict(type=AbstractCodegenASTNode)),
        ('PARAM', 'margin', dict(type=int, default=0)),
        ('PARAM', 'margin_top', dict(type=int, default=None, allow_none=True)),
        ('PARAM', 'margin_bottom', dict(type=int, default=None, allow_none=True)),
    )

    @property
    def effective_margins(self):
        return (
            self.margin if self.margin_top is None else self.margin_top,
            self.margin if self.margin_bottom is None else self.margin_bottom
        )

    def render(self, context):
        yield from self.content.render(context)


class NullNode(PromptableNode):
    """
    A node that renders nothing. You can substitute nodes in a sequence with NullNode to make them disappear.
    """
    AST_NODE_CONFIG = ()

    def render_promptable(self, _context, _prompt_width, _tail_width):
        yield from []


class ItemsList(AbstractCodegenASTNode):
    """
    A highly versatile construct used for rendering array items, object properties, method parameters, etc.

    Depending on the available space, and the nature of the items, the construct will choose between two possible
    representations (example is for joiner=", "):

    - Horizontal::

      item, item, item,
      item, item

    - Vertical::

      item,
      item,
      item

    Note: If any of the items is multiline, the vertical representation is the only one available.
    """
    AST_NODE_CONFIG = (
        ('CHILD_LIST', 'items', dict(type=PromptableNode)),
        ('PARAM', 'joiner', dict(type=str, default='')),
        ('PARAM', 'allow_horiz', dict(type=bool, default=True)),
        ('PARAM', 'allow_horiz_if_oneliner', dict(type=bool, default=False)),
        ('PARAM', 'trailing_comma', dict(type=bool, default=False)),
    )

    def render(self, context):
        item_renders = self._prepare_item_renders(context.derive(oneliner=True))

        allow_horiz = self.allow_horiz or (context.oneliner and self.allow_horiz_if_oneliner)

        if allow_horiz and all(len(item_render) <= 1 for item_render in item_renders):
            yield from self._render_horizontal(context, item_renders)
        else:
            yield from self._render_vertical(item_renders)

    def _split_joiner(self):
        joiner1 = self.joiner.rstrip()
        joiner2 = self.joiner[len(joiner1):]

        return joiner1, joiner2

    def _prepare_item_renders(self, context):
        # Note: it's very important that we do these steps in this exact order, even if it seems inefficient. The fact
        # that some items may turn out to be empty really complicates things.

        joiner1, _ = self._split_joiner()

        item_renders = [list(item.render_promptable(context, 0, len(joiner1))) for item in self.items]

        if not self.trailing_comma:
            last_nonempty = last_index_where(item_renders, lambda r: len(r) > 0)
            if last_nonempty is not None:
                # Last item does not have a comma and the associated tail space, redo its rendering
                item_renders[last_nonempty] = list(self.items[last_nonempty].render(context))

        item_renders = [render for render in item_renders if len(render) > 0]

        # Add commas
        for render in (item_renders if self.trailing_comma else item_renders[:-1]):
            render[-1] += joiner1

        return item_renders

    def _render_vertical(self, item_renders):
        for item in item_renders:
            yield from item

    def _render_horizontal(self, context, item_renders):
        _, joiner2 = self._split_joiner()

        buffer = ''

        for item_lines in item_renders:
            item = item_lines[0]

            # Try to add to current line
            candidate = buffer + ('' if buffer == '' else joiner2) + item
            if len(candidate) <= context.width:
                buffer = candidate
                continue

            # Commit line and start new one
            if buffer != '':
                yield buffer

            buffer = item

        if buffer != '':
            yield buffer


def seq0(*items):
    """Convenience function for instantiating a 0-margin Sequence"""
    return Sequence(items)


def seq1(*items):
    """Convenience function for instantiating a 1-margin Sequence"""
    return Sequence(items, items_margin=1)
