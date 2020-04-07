from atmfjstc.lib.py_lang_utils.iteration import iter_with_first_last

from atmfjstc.lib.abstract_codegen.ast.base import AbstractCodegenASTNode, PromptableNode


class BlockLike(PromptableNode):
    """
    A base for all block-like nodes. All block-likes have a head, tail, and content.

    Useful for arrays, objects, for, if, etc. constructs (esp. in combination with ItemsList).
    """
    AST_NODE_CONFIG = (
        'abstract',
        ('CHILD', 'content', dict(type=AbstractCodegenASTNode)),
        ('PARAM', 'head', dict(type=str, default='')),
        ('PARAM', 'tail', dict(type=str, default='')),
    )


class Block(BlockLike):
    """
    A construct for representing a block (an area delimited by symbols and/or indented).

    Useful for arrays, objects, for, if, etc. constructs (esp. in combination with ItemsList).
    """
    AST_NODE_CONFIG = (
        ('PARAM', 'allow_oneliner', dict(type=bool, default=True)),
    )

    def render_promptable(self, context, prompt_width, tail_width):
        if self.allow_oneliner:
            render = self._try_render_oneliner(context, prompt_width, tail_width)
            if render is not None:
                yield render
                return

        yield self.head.rstrip()

        for line in self.content.render(context.derive(sub_one_indent=True)):
            yield ' ' * context.indent + line

        if self.tail.lstrip() != '':
            # Note that we intentionally collapse an empty tail, but not an empty head
            yield self.tail.lstrip()

    def _try_render_oneliner(self, context, prompt_width, tail_width):
        avail_width = context.width - prompt_width - tail_width - len(self.head) - len(self.tail)
        if avail_width < 0:
            return None

        content_render = list(self.content.render(context.derive(width=avail_width, oneliner=True)))
        if len(content_render) > 1:
            return None

        if (len(content_render) == 0) or (content_render[0] == ''):
            return self.head.rstrip() + self.tail.lstrip()

        if len(content_render[0]) > avail_width:
            return None

        return self.head + content_render[0] + self.tail


class Brace(BlockLike):
    """
    Wraps an element and ensures that a specific head and tail are added to it.

    Useful for adding commas to elements, left-hand-side declarations to values etc.
    """
    AST_NODE_CONFIG = (
        ('CHILD', 'content', dict(type=AbstractCodegenASTNode)),
    )

    def render_promptable(self, context, prompt_width, tail_width):
        for line, is_first, is_last in iter_with_first_last(
            self.content.render_promptable(context, prompt_width + len(self.head), tail_width + len(self.tail))
        ):
            if is_first:
                line = (self.head + line).rstrip()
            if is_last:
                line += self.tail

            yield line
