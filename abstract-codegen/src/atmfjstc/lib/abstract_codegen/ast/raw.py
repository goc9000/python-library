import collections

from typing import Iterable

from atmfjstc.lib.text_utils import check_single_line

from atmfjstc.lib.abstract_codegen.CodegenContext import CodegenContext
from atmfjstc.lib.abstract_codegen.ast.base import PromptableNode


class Atom(PromptableNode):
    """
    A node containing an unbreakable bit of text without newlines, that will be rendered as-is wherever it appears.

    Note that an empty `Atom` is not the same as a `NullNode`. An `Atom` is always considered to take up space, and
    be considered "not-empty content" by blocks, etc. around it.
    """
    AST_NODE_CONFIG = (
        ('PARAM', 'content', dict(type=str, check=check_single_line)),
    )

    def render_promptable(self, _context: CodegenContext, _prompt_width: int, _tail_width: int) -> Iterable[str]:
        yield self.content


def _ensure_tuple(value):
    return tuple(value) if isinstance(value, collections.abc.Iterable) else value


def _check_lines_ok(lines):
    for line in lines:
        if not isinstance(line, str):
            raise TypeError("Value must be a tuple of strings")
        if '\n' in line:
            raise ValueError("Lines should not contain newline characters")


class PreformattedLines(PromptableNode):
    """
    A node containing preformatted lines that will be rendered as-is.

    Useful mainly as a temporary node to bridge AST-based rendering with old text-based rendering while the latter is
    being refactored.
    """
    AST_NODE_CONFIG = (
        ('PARAM', 'lines', dict(coerce=_ensure_tuple, type=tuple, check=_check_lines_ok)),
    )

    def render_promptable(self, _context: CodegenContext, _prompt_width: int, _tail_width: int) -> Iterable[str]:
        yield from self.lines


def pre(lines_iterable: Iterable[str]) -> PreformattedLines:
    """
    Convenience function for instantiationg a PreformattedLines node using an iterable of lines (list, generator etc.)
    """
    return PreformattedLines(lines_iterable)
