from textwrap import dedent, wrap

from atmfjstc.lib.text_utils import split_paragraphs

from atmfjstc.lib.abstract_codegen.ast.base import AbstractCodegenASTNode


class ReflowableText(AbstractCodegenASTNode):
    """
    A node that represents a block of text that can be reflowed so as to take up all the available width.

    Notes:

    - The text will automatically be dedent-ed (thus you can use triple-quote strings to specify it)
    - Lines of text separated by a single newline will be merged into a single reflowable paragraph. Paragraphs are
      separated by more than one newline.
    - This is particularly useful for the text inside comment blocks
    - Leading and trailing blank lines will be automatically removed
    - Do not put bulleted lists, etc. or other formatting inside the text, as they will not respond to the reflow
      correctly. Instead, represent the text using a Sequence of ReflowableText paragraphs and other nodes to represent
      the non-text content.
    """
    AST_NODE_CONFIG = (
        ('PARAM', 'text', dict(type=str)),
    )

    def render(self, context):
        parts = split_paragraphs(dedent(self.text).strip("\n"), keep_separators=True)

        for i in range(0, len(parts), 2):
            if i > 0:
                for _ in range(parts[i - 1].count('\n') - 1):
                    yield ''

            for line in wrap(parts[i].rstrip(), width=context.width):
                yield line


class WrapText(AbstractCodegenASTNode):
    """
    Adds decorations around text content (usually for turning it into a comment block).

    How it works:

    - The caller will specify a 'head', 'indent' and/or 'tail' (by default all are empty)
    - If the content is non-empty, the rendering will look like::

      <head>
      <indent>content line 1
      <indent>content line 2
      ...
      <tail>

    - If the content is empty, nothing will be generated (even if head and tail are non-empty)

    Notes:

    - This is particularly useful for comment blocks (e.g. for a classic doc comment, try head='/**', indent=' * ',
      tail=' */')
    """
    AST_NODE_CONFIG = (
        ('CHILD', 'content', dict(type=AbstractCodegenASTNode)),
        ('PARAM', 'indent', dict(type=str, default='')),
        ('PARAM', 'head', dict(type=str, default='')),
        ('PARAM', 'tail', dict(type=str, default='')),
    )

    def render(self, context):
        subcontext = context.derive(sub_width=len(self.indent))

        first = True

        for line in self.content.render(subcontext):
            if first and (self.head != ''):
                yield self.head

            yield (self.indent + line).rstrip()

            first = False

        if not first and (self.tail != ''):
            yield self.tail
