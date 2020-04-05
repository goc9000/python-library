class CodegenContext:
    _width = None
    _indent = None

    def __init__(self, width, indent=2):
        self._width = width
        self._indent = indent

    @property
    def width(self):
        return self._width

    @property
    def indent(self):
        return self._indent

    def derive(self, width=None, indent=None, add_width=0, sub_width=0, sub_one_indent=False):
        def coalesce(a, b):
            return a if b is None else b

        return CodegenContext(
            width=coalesce(self.width, width) + add_width - sub_width - (self.indent if sub_one_indent else 0),
            indent=coalesce(self.indent, indent),
        )
