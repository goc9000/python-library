from dataclasses import dataclass


@dataclass(frozen=True)
class CodegenContext:
    width: int
    indent: int = 2
    oneliner: bool = False  # Request a oneliner rendering if available

    def derive(self, width=None, indent=None, add_width=0, sub_width=0, sub_one_indent=False, oneliner=None):
        def coalesce(a, b):
            return a if b is None else b

        return CodegenContext(
            width=coalesce(self.width, width) + add_width - sub_width - (self.indent if sub_one_indent else 0),
            indent=coalesce(self.indent, indent),
            oneliner=coalesce(self.oneliner, oneliner),
        )
