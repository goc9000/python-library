"""
Miscellaneous utilities for working with dicts.
"""


def copy_only_fields(source_dict, fields):
    return { k: v for k, v in source_dict.items() if k in fields }
