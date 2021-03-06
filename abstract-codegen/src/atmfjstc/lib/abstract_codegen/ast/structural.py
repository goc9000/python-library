from abc import abstractmethod
from typing import Iterable, Tuple

from atmfjstc.lib.text_utils import iter_wrap_items

from atmfjstc.lib.abstract_codegen.CodegenContext import CodegenContext
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
    - Margins do not apply between an item and the top/bottom of the `Sequence` itself.
    - Margins are ignored for an item that is empty (produces no lines)
    """
    AST_NODE_CONFIG = (
        ('CHILD_LIST', 'content', dict(type=AbstractCodegenASTNode)),
        ('PARAM', 'items_margin', dict(type=int, default=0)),
    )

    def render(self, context: CodegenContext) -> Iterable[str]:
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
    def effective_margins(self) -> Tuple[int, int]:
        return (
            self.margin if self.margin_top is None else self.margin_top,
            self.margin if self.margin_bottom is None else self.margin_bottom
        )

    def render(self, context: CodegenContext) -> Iterable[str]:
        yield from self.content.render(context)


class NullNode(PromptableNode):
    """
    A node that renders nothing and is, in general, equivalent to no node at all being present in its position.

    You can substitute child nodes in a `Sequence`, `ChainedBlocks`, `ItemsList`, `Brace` etc. with `NullNode` to make
    them disappear when it is inelegant to just omit the node upon some condition being true.
    """
    AST_NODE_CONFIG = ()

    def render_promptable(self, _context: CodegenContext, _prompt_width: int, _tail_width: int) -> Iterable[str]:
        yield from []


class ItemsListBase(AbstractCodegenASTNode):
    AST_NODE_CONFIG = (
        'abstract',
        ('CHILD_LIST', 'items', dict(type=PromptableNode)),
        ('PARAM', 'joiner', dict(type=str, default='')),
        ('PARAM', 'allow_horiz', dict(type=bool, default=True)),
        ('PARAM', 'allow_horiz_if_oneliner', dict(type=bool, default=False)),
    )

    _joiner1 = None
    _joiner2 = None

    def _post_init(self):
        self._joiner1, self._joiner2 = self._split_joiner()

    def render(self, context: CodegenContext) -> Iterable[str]:
        item_renders = self._prepare_item_renders(context)

        allow_horiz = self.allow_horiz or (context.oneliner and self.allow_horiz_if_oneliner)

        if allow_horiz and all(len(item_render) <= 1 for item_render in item_renders):
            yield from self._render_horizontal(context, item_renders)
        else:
            yield from self._render_vertical(item_renders)

    @abstractmethod
    def _split_joiner(self):
        """
        Splits the joiner into two parts:

        - The part that is always added to an item (unless it is the last)
        - The part that is only added between an item and the previous one, when it is not the first in line
        """

    def _prepare_item_renders(self, context):
        item_renders = [self._render_item(item, context) for item in self.items]

        # Filter out empty renders and their corresponding items
        filtered = [(render, item) for render, item in zip(item_renders, self.items) if len(render) > 0]
        item_renders, items = [pair[0] for pair in filtered], [pair[1] for pair in filtered]

        extreme_item_index = self._get_extreme_item_index(len(items), context)
        if extreme_item_index is not None:
            item_renders[extreme_item_index] = self._render_item(items[extreme_item_index], context, True)

        return item_renders

    @abstractmethod
    def _get_extreme_item_index(self, n_items, context):
        """Note, an item is "extreme" if the joiner/comma should not be added to it (e.g. it is the last)"""

    @abstractmethod
    def _render_item(self, item, context, is_extreme=False):
        pass

    def _render_vertical(self, item_renders):
        for item in item_renders:
            yield from item

    def _render_horizontal(self, context, item_renders):
        yield from iter_wrap_items((render[0] for render in item_renders), context.width, separator=self._joiner2)


class ItemsList(ItemsListBase):
    """
    A highly versatile construct used for rendering array items, object properties, method parameters, etc.

    Depending on the available space, and the nature of the items, the construct will choose between two possible
    representations (example is for joiner=``", "``):

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
        ('PARAM', 'trailing_comma', dict(type=bool, default=False)),
    )

    def _split_joiner(self):
        joiner1 = self.joiner.rstrip()
        joiner2 = self.joiner[len(joiner1):]

        return joiner1, joiner2

    def _get_extreme_item_index(self, n_items, _context):
        return (n_items - 1) if ((n_items > 0) and not self.trailing_comma) else None

    def _render_item(self, item, context, is_extreme=False):
        render = list(item.render_promptable(context.derive(oneliner=True), 0, 0 if is_extreme else len(self._joiner1)))

        if (len(render) > 0) and not is_extreme:
            render[-1] += self._joiner1

        return render


class UnionItemsList(ItemsListBase):
    """
    A variant of ItemsList with some display tweaks suitable for rendering union/intersection items.

    Possible representations will look like this (example is for joiner=``' | '``):

    - Horizontal, one-liner::

          item | item | item

    - Horizontal, block/multiline::

          | item | item | item
          | item | item

    - Vertical::

          | item
          | item
          | (big..
            ..item)
          | item

    Note: If any of the items is multiline, the vertical representation is the only one available.
    """
    AST_NODE_CONFIG = (
    )

    def _split_joiner(self):
        joiner1 = self.joiner.lstrip()
        joiner2 = self.joiner[:-len(joiner1)]

        return joiner1, joiner2

    def _get_extreme_item_index(self, n_items, context):
        return 0 if (context.oneliner and (n_items > 0)) else None

    def _render_item(self, item, context, is_extreme=False):
        joiner1, _ = self._split_joiner()

        render = list(item.render(context.derive(oneliner=True, sub_width=0 if is_extreme else len(joiner1))))

        if (len(render) > 0) and not is_extreme:
            render = [joiner1 + render[0], *[' ' * len(joiner1) + line for line in render[1:]]]

        return render


def seq0(*items: AbstractCodegenASTNode) -> Sequence:
    """Convenience function for instantiating a 0-margin Sequence"""
    return Sequence(items)


def seq1(*items: AbstractCodegenASTNode) -> Sequence:
    """Convenience function for instantiating a 1-margin Sequence"""
    return Sequence(items, items_margin=1)
