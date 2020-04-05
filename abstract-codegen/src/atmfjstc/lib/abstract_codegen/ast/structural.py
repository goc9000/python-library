from atmfjstc.lib.abstract_codegen.ast.base import AbstractCodegenASTNode


class Sequence(AbstractCodegenASTNode):
    """
    A vertical sequence of sections that are rendered one after the other.

    Notes:

    - This is the main workhorse that is generally used to organize the top-level content of a file, or the code inside
      methods, procedures etc.
    """
    AST_NODE_CONFIG = (
        ('CHILD_LIST', 'content', dict(type=AbstractCodegenASTNode)),
    )

    def render(self, context):
        for section in self.content:
            for line in section.render(context):
                yield line
