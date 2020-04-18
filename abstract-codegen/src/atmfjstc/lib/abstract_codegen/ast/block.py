import itertools

from atmfjstc.lib.py_lang_utils.iteration import iter_with_first_last, iter_with_last
from atmfjstc.lib.text_utils import check_single_line

from atmfjstc.lib.abstract_codegen.ast.base import AbstractCodegenASTNode, PromptableNode
from atmfjstc.lib.abstract_codegen.ast.raw import Atom
from atmfjstc.lib.abstract_codegen.ast.structural import NullNode


class BlockLike(PromptableNode):
    """
    A base for all block-like nodes. All block-likes have a head, tail, and content.

    Useful for arrays, objects, for, if, etc. constructs (esp. in combination with ItemsList).
    """
    AST_NODE_CONFIG = (
        'abstract',
        ('CHILD', 'content', dict(type=AbstractCodegenASTNode)),
        ('PARAM', 'head', dict(type=str, check=check_single_line, default='')),
        ('PARAM', 'tail', dict(type=str, check=check_single_line, default='')),
    )


class Block(BlockLike):
    """
    A construct for representing a block (an area delimited by symbols and/or indented).

    Useful for arrays, objects, for, if, etc. constructs (esp. in combination with ItemsList).

    Notes:

    - The `head` and `tail` cannot be multiline. If you need something like a multiline head or tail, consider using
      the `ChainedBlocks` node
    """
    AST_NODE_CONFIG = (
        ('PARAM', 'allow_oneliner', dict(type=bool, default=True)),
    )

    def render_promptable(self, context, prompt_width, tail_width):
        if self.allow_oneliner:
            render = self._try_render_oneliner(context, prompt_width, tail_width)
            if render is not None:
                yield render
                return

        yield self.head.rstrip()

        for line in self.content.render(context.derive(sub_one_indent=True, oneliner=False)):
            yield ' ' * context.indent + line

        if self.tail.lstrip() != '':
            # Note that we intentionally collapse an empty tail, but not an empty head
            yield self.tail.lstrip()

    def _try_render_oneliner(self, context, prompt_width, tail_width):
        avail_width = context.width - prompt_width - tail_width - len(self.head) - len(self.tail)
        if avail_width < 0:
            return None

        content_render = list(self.content.render(context.derive(width=avail_width, oneliner=True)))
        if len(content_render) > 1:
            return None

        if (len(content_render) == 0) or (content_render[0] == ''):
            return self.head.rstrip() + self.tail.lstrip()

        if len(content_render[0]) > avail_width:
            return None

        return self.head + content_render[0] + self.tail


class Brace(BlockLike):
    """
    Wraps an element and ensures that a specific head and tail are added to it.

    Useful for adding commas to elements, left-hand-side declarations to values etc.

    Notes:

    - The content must be promptable (thus it is a more restricted type than for a general BlockLike)
    - The `head` and `tail` cannot be multiline. If you need something like a multiline head or tail, consider using
      the `ChainedBlocks` node
    """
    AST_NODE_CONFIG = (
        ('CHILD', 'content', dict(type=PromptableNode)),
    )

    def render_promptable(self, context, prompt_width, tail_width):
        for line, is_first, is_last in iter_with_first_last(
            self.content.render_promptable(context, prompt_width + len(self.head), tail_width + len(self.tail))
        ):
            if is_first:
                line = (self.head + line).rstrip()
            if is_last:
                line += self.tail

            yield line


class ChainedBlocks(PromptableNode):
    """
    A construct that intelligently chains multiple blocks together.

    This is highly useful for complex constructs such as if statements, methods, etc. For a function, for instance,
    the first block would be the parameters between the (), while the second is the code between the {}.

    The sequence of blocks to be rendered is described by four kinds of child nodes:

    - `BlockLike` nodes are the blocks themselves
    - `Atom` nodes will be merged with the tail of the previous block and the head of the next block (as well as with
      other adjacent `Atom` nodes)
    - `NullNode`'s will simply be ignored (they are useful for when just omitting the node is inelegant)
    - `ChainedBlock` nodes will add their own blocks and delimiters to their place in the list
    """
    # Note: we set AST_NODE_CONFIG after the class definition, due to the self-reference

    def render_promptable(self, context, prompt_width, tail_width):
        blocks, delimiters = self._consolidate()

        last_line = delimiters[0]
        effective_prompt_width = 0

        for block, prev_delim, next_delim in zip(blocks, delimiters[:-1], delimiters[1:]):
            effective_block = block.alter(head=last_line, tail=next_delim)

            for line, is_last in iter_with_last(
                effective_block.render_promptable(context, effective_prompt_width, tail_width)
            ):
                if not is_last:
                    yield line
                    effective_prompt_width = 0
                else:
                    last_line = line

        yield last_line

    def _consolidate(self):
        delimiters = []
        blocks = []

        for is_delim, parts in itertools.groupby(self._iter_raw_items(), lambda item: isinstance(item, str)):
            parts = list(parts)

            if is_delim:
                delimiters.append(''.join(parts))
            else:
                assert len(parts) == 1
                blocks.append(parts[0])

        assert len(delimiters) == len(blocks) + 1

        return blocks, delimiters

    def _iter_raw_items(self):
        def _iter_chain_content(content):
            for item in content:
                if isinstance(item, NullNode):
                    continue
                elif isinstance(item, Atom):
                    yield item.content
                elif isinstance(item, ChainedBlocks):
                    yield from _iter_chain_content(item.content)
                else:
                    yield item.head
                    yield item
                    yield item.tail

        yield ''
        yield from _iter_chain_content(self.content)
        yield ''


ChainedBlocks.AST_NODE_CONFIG = (
    ('CHILD_LIST', 'content', dict(type=(Atom, BlockLike, ChainedBlocks, NullNode))),
)
