from atmfjstc.lib.abstract_codegen.ast.base import AbstractCodegenASTNode


class Atom(AbstractCodegenASTNode):
    """
    A node containing a single line of text that will be returned as-is.
    """
    AST_NODE_CONFIG = (
        ('PARAM', 'content', dict(type=str)),
    )

    def _sanity_check_post_init(self):
        assert "\n" not in self.content

    def render(self, context):
        yield self.content


class PreformattedLines(AbstractCodegenASTNode):
    """
    A node containing preformatted lines that will be returned as-is.

    Useful mainly as a temporary node to bridge AST-based rendering with old text-based rendering while the latter is
    being refactored.
    """
    AST_NODE_CONFIG = (
        ('PARAM', 'lines', dict(type=(list, tuple))),
    )

    def render(self, context):
        for line in self.lines:
            yield line
