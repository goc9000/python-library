"""
Private module grouping all the functions for generating an AST node's repr() representation.
"""

from atmfjstc.lib.ast import ASTNode
from atmfjstc.lib.py_lang_utils.iteration import iter_with_last


def render_ast_node_repr(node, indent='  '):
    return "\n".join(_render_ast_node_repr(node, indent))


def _render_ast_node_repr(node, indent):
    field_renders = list()

    for field, value in node.all_field_values():
        if value == field.default:
            continue

        field_renders.append(_add_prompt(_render_ast_node_repr_value(value, indent), field.name + '='))

    return _render_block(node.__class__.__name__ + '(', ')', field_renders, indent)


def _render_ast_node_repr_value(value, indent):
    if isinstance(value, ASTNode):
        return _render_ast_node_repr(value, indent)
    if isinstance(value, (list, tuple)):
        return _render_block(
            '[', ']',
            [_render_ast_node_repr_value(item, indent) for item in value],
            indent
        )
    if isinstance(value, dict):
        return _render_block(
            '{', '}',
            [_add_prompt(_render_ast_node_repr_value(val, indent), repr(key)+': ') for key, val in value],
            indent
        )

    return repr(value).split("\n")


def _render_block(head, tail, rendered_items, indent):
    oneliner = _try_oneliner(head, tail, rendered_items)
    if oneliner is not None:
        return [oneliner]

    result = [head]

    for rendered_item, is_last_item in iter_with_last(rendered_items):
        for line, is_last_line in iter_with_last(rendered_item):
            result.append(indent + line + (',' if is_last_line and not is_last_item else ''))

    result.append(tail)

    return result


def _try_oneliner(head, tail, rendered_items):
    if any(len(item) > 1 for item in rendered_items):
        return None

    candidate = head + ', '.join(item[0] for item in rendered_items) + tail

    return candidate if ((len(rendered_items) == 0) or len(candidate) <= 40) else None


def _add_prompt(rendered_value, prompt):
    return [prompt + rendered_value[0], *rendered_value[1:]]
