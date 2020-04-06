class CodegenContext:
    _width = None
    _indent = None
    _oneliner = None  # Request a oneliner rendering if available

    def __init__(self, width, indent=2, oneliner=False):
        self._width = width
        self._indent = indent
        self._oneliner = oneliner

    @property
    def width(self):
        return self._width

    @property
    def indent(self):
        return self._indent

    @property
    def oneliner(self):
        return self._oneliner

    def derive(self, width=None, indent=None, add_width=0, sub_width=0, sub_one_indent=False, oneliner=None):
        def coalesce(a, b):
            return a if b is None else b

        return CodegenContext(
            width=coalesce(self.width, width) + add_width - sub_width - (self.indent if sub_one_indent else 0),
            indent=coalesce(self.indent, indent),
            oneliner=coalesce(self.oneliner, oneliner),
        )
