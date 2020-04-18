from abc import ABCMeta, abstractmethod
from typing import Iterable

from atmfjstc.lib.ast import ASTNode

from atmfjstc.lib.abstract_codegen.CodegenContext import CodegenContext


class AbstractCodegenASTNode(ASTNode, metaclass=ABCMeta):
    """
    Base class for all AST nodes used to assemble the intermediate representation of a generated file.
    """
    AST_NODE_CONFIG = ('abstract',)

    @abstractmethod
    def render(self, context: CodegenContext) -> Iterable[str]:
        """
        Renders this node (i.e. converts it to text) within a given context (width, indent size etc.)

        Note that the rendering is done line-by-line and, where possible, in a lazy manner. It is possible, in
        principle, to stop midway through reading the lines and not have the renderer do the work for the rest, if
        we have already got what we need.

        Args:
            context: A CodegenContext object containing the available width, indent size etc.

        Returns:
            The generated text for this node, as a stream of lines. The lines are not newline-terminated.
        """
        raise NotImplementedError


class PromptableNode(AbstractCodegenASTNode):
    """
    Base class for nodes that are capable of rendering within a specific kind of non-rectangular space.

    Normally nodes attempt to render within a rectangular space of `context.width` columns across. In some situations,
    however, the real available space has a special shape: it is a rectangle of `context.width` columns across as
    before, but some of the leftmost columns in first line are reserved (this space is called the *prompt*), as well as
    some of the rightmost columns in the last line (this space is called the *tail*). This often happens for items
    inside an array (e.g. they need to reserve space for the comma) or object properties (the property name is the
    prompt).

    Since only certain kinds of structures can support this sort of complex rendering, we mark them by making them
    derive from this node type.
    """
    AST_NODE_CONFIG = ('abstract',)

    def render(self, context):
        return self.render_promptable(context, 0, 0)

    @abstractmethod
    def render_promptable(self, context: CodegenContext, prompt_width: int, tail_width: int) -> Iterable[str]:
        """
        The `render` method as extended for "promptable" nodes. It takes two extra parameters corresponding to the more
        complicated rendering context.

        Args:
            context: A CodegenContext object containing the available width, indent size etc.
            prompt_width: The number of columns unavailable at the start of the first (or only) line
            tail_width: The number of columns unavailable at the end of the last (or only) line

        Returns:
            The generated text for this node, as a stream of lines. The lines are not newline-terminated.
        """
        raise NotImplementedError
