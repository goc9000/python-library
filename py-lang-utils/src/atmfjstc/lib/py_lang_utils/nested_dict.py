"""
Miscellaneous utilities for working with nested dict structures.
"""


def get_in_nested_dict(source_dict, path, fallback_value=None):
    """
    Gets a value in a nested dict, given its path.

    If the path does not exist, returns fallback_value (default None)
    """
    if len(path) == 0:
        return source_dict

    ptr = source_dict

    for item in path[:-1]:
        ptr = ptr.get(item)
        if not isinstance(ptr, dict):
            return fallback_value

    return ptr.get(path[-1], fallback_value)


def set_in_nested_dict(mut_dict, path, value):
    """
    Sets a value in a nested dict, at a given path. Inner dicts will automatically be created as needed.
    """
    assert len(path) > 0

    ptr = mut_dict

    for item in path[:-1]:
        if not isinstance(ptr, dict):
            raise ValueError("Invalid path {} for setting in a nested dict".format(path))

        if item not in ptr:
            ptr[item] = mut_dict.__class__()  # So we can handle OrderedDict etc.

        ptr = ptr[item]

    if not isinstance(ptr, dict):
        raise ValueError("Invalid path {} for setting in a nested dict".format(path))

    ptr[path[-1]] = value


def get_or_init_in_nested_dict(mut_dict, path, constructor):
    """
    Gets a value at a certain path in a nested dict, creating it and all parent dicts if missing.
    """
    value = get_in_nested_dict(mut_dict, path)
    if value is not None:
        return value

    value = constructor()

    set_in_nested_dict(mut_dict, path, value)

    return value


def accumulate_in_nested_dict(mut_dict, path, value):
    """
    Convenience function for creating and adding value to a list inside a nested dict.
    """
    get_or_init_in_nested_dict(mut_dict, path, list).append(value)
