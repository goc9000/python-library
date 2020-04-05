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
        pass
