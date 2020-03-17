from atmfjstc.lib.py_lang_utils.token import Token


NVP = Token(repr_="NVP")
"""
NVP (No Value Provided) is used as a token to indicate no value was provided, in places where None is a valid value.
"""


def parse_ast_node_args(field_defs, args, kwargs):
    result = dict()
    matched_args = _match_up_provided_args_with_field_defs(field_defs, args, kwargs)

    for arg, field_def in zip(matched_args, field_defs):
        result[field_def.name] = field_def.prepare_field_value(arg)

    return result


def _match_up_provided_args_with_field_defs(field_defs, args, kwargs):
    """
    Returns a list of provided values, aligned with the field definitions. Missing values are represented using the NVP
    (No Value Provided) token (as None can be a valid provided value).
    """
    values = [NVP] * len(field_defs)

    n_positional_params = 0
    arg_to_field_index = dict()

    for field_index, field_def in enumerate(field_defs):
        arg_to_field_index[field_def.name] = field_index

        if field_def.kw_only:
            continue

        arg_to_field_index[n_positional_params] = field_index
        n_positional_params += 1

    if len(args) > n_positional_params:
        raise ValueError("Too many positional args provided ({} vs a max of {})".format(len(args), n_positional_params))

    for arg_index, arg in enumerate(args):
        values[arg_to_field_index[arg_index]] = arg

    for arg_key, arg in kwargs.items():
        field_index = arg_to_field_index.get(arg_key)
        if field_index is None:
            raise ValueError("Unknown field '{}'".format(arg_key))
        if values[field_index] != NVP:
            raise ValueError("Field '{}' was specified as both positional and keyword arguments".format(arg_key))

        values[field_index] = arg

    return values
