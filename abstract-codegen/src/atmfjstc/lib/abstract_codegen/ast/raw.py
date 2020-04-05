from atmfjstc.lib.abstract_codegen.ast.base import PromptableNode


class Atom(PromptableNode):
    """
    A node containing a single line of text that will be returned as-is.
    """
    AST_NODE_CONFIG = (
        ('PARAM', 'content', dict(type=str)),
    )

    def _sanity_check_post_init(self):
        assert "\n" not in self.content

    def render_promptable(self, _context, _prompt_width, _tail_width):
        yield self.content


class PreformattedLines(PromptableNode):
    """
    A node containing preformatted lines that will be returned as-is.

    Useful mainly as a temporary node to bridge AST-based rendering with old text-based rendering while the latter is
    being refactored.
    """
    AST_NODE_CONFIG = (
        ('PARAM', 'lines', dict(type=(list, tuple))),
    )

    def render_promptable(self, _context, _prompt_width, _tail_width):
        yield from self.lines


def pre(lines_iterable):
    """
    Convenience function for instantiationg a PreformattedLines node using an iterable of lines (list, generator etc.)
    """
    return PreformattedLines(list(lines_iterable))
