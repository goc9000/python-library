"""
Miscellaneous utilities for working with nested dict (or Mapping in general) structures.
"""

from typing import Any, Callable, Optional

from collections.abc import Mapping, MutableMapping, Sequence


DictFactory = Callable[[], MutableMapping]


def get_in_nested_dict(source_dict: Any, path: Sequence, fallback_value: Any = None) -> Any:
    """
    Gets a value in a nested dict (or Mapping), given its path.

    If the path does not exist, returns fallback_value (default None)

    If the path is empty, the source value itself will be returned, in which case it can be of any type.
    """
    if len(path) == 0:
        return source_dict

    ptr = source_dict

    for item in path[:-1]:
        ptr = ptr.get(item)
        if not isinstance(ptr, Mapping):
            return fallback_value

    return ptr.get(path[-1], fallback_value)


def set_in_nested_dict(mut_dict: Mapping, path: Sequence, value: Any, factory: Optional[DictFactory] = None):
    """
    Sets a value in a nested dict, at a given path. Inner dicts will automatically be created as needed.

    The function works for other kinds of MutableMapping's too. In this case, when the function needs to create a
    nested mapping in some other mapping of type A, it will try to instantiate an A() class too. To override this, use
    the `factory=` parameter to specify the class that will be called instead.

    It is acceptable for the path to traverse read-only mappings if the structure is already created (thus, it can
    write to mutable dict-likes nested inside read-only dict-likes)
    """
    if len(path) == 0:
        raise ValueError("Path must be non-empty when setting a value in a nested dict")

    ptr = mut_dict
    path_so_far = []

    for item in path[:-1]:
        if not isinstance(ptr, Mapping):
            raise ValueError(f"Trying to set a value at {path}, but item at {path_so_far} is not dict-like")

        if item not in ptr:
            if not isinstance(ptr, MutableMapping):
                raise ValueError(f"Trying to set a value at {path}, but dict at {path_so_far} is read-only")

            ptr[item] = (factory or ptr.__class__)()

        ptr = ptr.get(item)
        path_so_far.append(item)

    if not isinstance(ptr, MutableMapping):
        raise ValueError(f"Trying to set a value at {path}, but the dict there is read-only")

    ptr[path[-1]] = value


def get_or_init_in_nested_dict(
    mut_dict: Mapping, path: Sequence, constructor: Callable[[], Any], dict_factory: Optional[DictFactory] = None
) -> Any:
    """
    Gets a value at a certain path in a nested dict/mapping, creating it and all parent dicts if missing.
    """
    value = get_in_nested_dict(mut_dict, path)
    if value is not None:
        return value

    value = constructor()

    set_in_nested_dict(mut_dict, path, value, factory=dict_factory)

    return value


def accumulate_in_nested_dict(
    mut_dict: Mapping, path: Sequence, value: Any, dict_factory: Optional[DictFactory] = None
):
    """
    Convenience function for creating and adding value to a list inside a nested dict.
    """
    get_or_init_in_nested_dict(mut_dict, path, list, dict_factory=dict_factory).append(value)
