from abc import ABCMeta, abstractmethod

from atmfjstc.lib.ast import ASTNode


class AbstractCodegenASTNode(ASTNode, metaclass=ABCMeta):
    """
    Base class for all AST nodes used to assemble the intermediate representation of a generated file.
    """
    AST_NODE_CONFIG = ('abstract',)

    @abstractmethod
    def render(self, context):
        """
        A generator that yields every line in the rendered representation of this node.
        """


class PromptableNode(AbstractCodegenASTNode):
    """
    Base class for nodes that are capable of rendering within a specific kind of non-rectangular space.

    Normally nodes attempt to render within a rectangular space of context.width columns across. In some situations,
    however, the real available space has a special shape: it is a rectangle of context.width columns across as before,
    but some of the leftmost columns in first line are reserved (this space is called the prompt), as well as some of
    the rightmost columns in the last line (this space is called the tail). This often happens for items inside an
    array (e.g. they need to reserve space for the comma) or object properties (the property name is the prompt).

    Since only certain kinds of structures can support this sort of complex rendering, we mark them by making them
    derive from this node type.
    """
    AST_NODE_CONFIG = ('abstract',)

    def render(self, context):
        return self.render_promptable(context, 0, 0)

    @abstractmethod
    def render_promptable(self, context, prompt_width, tail_width):
        pass
