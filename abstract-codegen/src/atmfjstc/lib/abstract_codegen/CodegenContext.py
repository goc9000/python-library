from dataclasses import dataclass


@dataclass(frozen=True)
class CodegenContext:
    """
    Holds options that control how the rendering of an abstract codegen AST node is done.

    For safety, objects of this type are immutable. To "modify" a context, you can create an altered copy by calling
    its `derive` function, similar to how one would call `replace` for a named tuple.

    Attributes:
        width: The number of columns available for rendering the code. The renderer will do its best to ensure that
            the code fits this width, but note that success is not guaranteed in all cases.
        indent: The number of columns by which code inside blocks will be indented
        oneliner: Signal that a one-liner rendering is preferable. A node may or may not be able to honor this,
            depending on its type, content, and available width.
    """

    width: int
    indent: int = 2
    oneliner: bool = False

    def derive(self, width=None, indent=None, add_width=0, sub_width=0, sub_one_indent=False, oneliner=None):
        """
        Creates a modified copy of this rendering context (contexts are otherwise immutable).

        Args:
            width: The new width for the context (or None to leave it unchanged)
            indent: The new indent size for the context (or None to leave it unchanged)
            add_width: The number of columns to add to the width
            sub_width: The number of columns to subtract from the width
            sub_one_indent: Subtracts the indent size from the available width (a very common operation)
            oneliner: The new 'request oneliner' flag for the context (or None to leave it unchanged)

        Returns:
            A context with the modifications performed.
        """
        def coalesce(a, b):
            return a if b is None else b

        return CodegenContext(
            width=coalesce(self.width, width) + add_width - sub_width - (self.indent if sub_one_indent else 0),
            indent=coalesce(self.indent, indent),
            oneliner=coalesce(self.oneliner, oneliner),
        )
