from atmfjstc.lib.abstract_codegen.ast.base import AbstractCodegenASTNode


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
