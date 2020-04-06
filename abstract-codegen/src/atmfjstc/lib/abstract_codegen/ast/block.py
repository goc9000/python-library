from atmfjstc.lib.abstract_codegen.ast.base import AbstractCodegenASTNode, PromptableNode


class Block(PromptableNode):
    """
    A construct for representing a block (an area delimited by symbols and/or indented).

    Useful for arrays, objects, for, if, etc. constructs (esp. in combination with ItemsList).
    """
    AST_NODE_CONFIG = (
        ('CHILD', 'content', dict(type=AbstractCodegenASTNode)),
        ('PARAM', 'head', dict(type=str, default='')),
        ('PARAM', 'tail', dict(type=str, default='')),
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
