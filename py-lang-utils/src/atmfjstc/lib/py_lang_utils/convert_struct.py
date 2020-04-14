from typing import Callable, Optional, Hashable
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from atmfjstc.lib.py_lang_utils.token import Token


_NO_VALUE = Token()


def make_struct_converter(source_type, dest_type, fields, return_unparsed=False, ignore=(), none_means_missing=True):
    """
    General purpose utility for making functions that convert from a simple structure in class or dict format, to a
    dict format with similar fields, optionally renaming, converting or checking fields as they are accessed.

    The Source and Destination Types
    --------------------------------

    - `source_type` can be one of:

      - `dict`: Any type whose fields can be read with `obj.get('field_name')`, such as a `dict` or, more generally, a
        `Mapping`.
      - `class`: Any type whose fields can be read with `obj.field_name`, such as any class.

    - `destination_type` can be one of:

      - `dict`: The converter will return a new `dict` containing the converted fields.
      - `dict-by-reference`, `class-by-reference`: The converter will receive an existing `dict` or class and write
        converted fields to it accordingly.

    Field Specifications
    --------------------

    The `fields` parameter shapes the heart of the conversion algorithm. It is a `dict` where the keys are the names
    of the fields that are to be written to the destination, linked to field specification descriptions that describe
    how to obtain the converted value for each field.

    A field specification is normally a `dict` with one or more of these fields:

    - `src`: Specifies which field in the source we will be getting the value from. By default, a field will try to
      get its value from a source field of the same name.
    - `req`: If set to True, marks this field as required, meaning that an error will be thrown at runtime if the
      corresponding field in the source is missing. By default, fields are not required which means they will be
      skipped (not set in the destination) if the source field is missing.
    - `skip_empty`: If set to True (default false), the field will be skipped if it has an "empty" value, i.e. 0, False,
      None, or an empty collection.
    - `skip_if`: The field will be skipped if it is equal to this value.
    - `if_different`: Specifies a field in the source to which this field will be compared. It will be skipped unless
      it is different. Useful for backing up values.
    - `convert`: Specifies a function that will be called to convert this field's value before writing it to the
      destination. Applies only if the field is not skipped, and only after the previous tests.

      You can also specify the following strings that refer to built-in converters:

      - `utf8`: Decodes strings encoded as UTF-8 in a `bytes` value
      - `hex`: Converts a `bytes` value to a hex string

    - `store`: Any value specified here will be stored at the destination regardless of what the value read from the
      source was. Equivalent to a converter that only returns a fixed value. Mutually exclusive with `convert`.

    Alternatively, one can instead provide a dict like `dict(ignore=True)` which will cause the field in the source
    with that name to be ignored. This has the same effect as not specifying the field at all, but this affects the
    set of fields that are considered to be 'unparsed' (see the `return_unparsed` options).

    Field Specification Shortcuts
    -----------------------------

    Instead of specifying the full `dict`-based field specification, you can save typing by using these shortcuts
    when appropriate:

    - `True` or `None` or `''`: Equivalent to `dict()` (a field with all the default options)
    - `False`: Equivalent to `dict(ignore=True)`
    - `'option'`: Equivalent to `dict(option=True)`. Often use as `'req'` to specify fields that are required but have
      no other special processing.
    - `(shortcut, shortcut, ...)`: Equivalent to combining the other shortcuts into a single dict. E.g.::

      ('req', 'skip_empty', dict(convert='hex'))

      is equivalent to::

      dict(req=True, skip_empty=True, convert='hex')

    Other Options
    -------------

    - `none_means_missing`: If True (the default), a field is also considered 'missing' (for the purposes of `req`,
      etc.) if it has a value of None, which is a common convention in classes.

    - `return_unparsed`: If True, the converter will keep track of all the fields in the source that it has no
      instructions on how to parse, and report them alongside the normal result. This is useful for detecting unexpected
      data that one might want to add processing for in the future, or decide to ignore explicitly.

      Note that this only works for `dict`-type sources, as classes do not have a standardized way of getting a list
      of all their fields which are intended to represent data.

    - `ignore`: A list of additional field names that should be ignored, in addition to those marked as such in the
      `fields`.

    Return Value
    ------------

    The function returns a converter function that can be called like this:

    - For destinations of type 'dict':

      - With `return_unparsed` unset::

        result_dict = convert(source_class_or_dict)

      - With `return_unparsed` set::

        result_dict, unparsed_fields = convert(source_class_or_dict)

    - For destinations of type '*-by-reference':

      - With `return_unparsed` unset::

        convert(dest_class_or_dict, source_class_or_dict)

      - With `return_unparsed` set::

        unparsed_fields = convert(dest_class_or_dict, source_class_or_dict)

    Exceptions
    ----------

    - All compile-time errors (e.g. wrong setup) cause a `ConvertStructCompileError` to be thrown (possibly chained to
      other underlying exceptions)
    - All runtime errors (bad data) cause a `ConvertStructRuntimeError` subclass to be thrown.
    """

    field_specs, unhandled_getter = _parse_fields_and_setup_unhandled_getter(fields, ignore)
    source_dest_finder = _setup_source_dest_finder(dest_type)
    getter = _setup_field_getter(source_type, none_means_missing)
    setter = _setup_field_setter(dest_type)
    result_extractor = _setup_result_extractor(source_type, dest_type, return_unparsed, unhandled_getter)

    return _setup_conversion_core(field_specs, source_dest_finder, getter, setter, result_extractor)


def _parse_fields(fields):
    out_fields = []
    ignored_fields = set()

    for field, raw_field_spec in fields.items():
        try:
            parsed_field_spec = ConvertStructFieldSpec.parse(raw_field_spec, field)

            if parsed_field_spec is not None:
                out_fields.append((field, parsed_field_spec))
            else:
                ignored_fields.add(field)
        except Exception as e:
            raise ConvertStructCompileError(f"Invalid field spec for field '{field}'") from e

    return out_fields, ignored_fields


def _parse_fields_and_setup_unhandled_getter(fields, ignore_fields_option):
    field_specs, ignored = _parse_fields(fields)

    all_srcs = set(field_specs.source for _, field_specs in field_specs) | set(ignore_fields_option or set()) | ignored

    def unhandled_getter(source_dict):
        if not isinstance(source_dict, Mapping):
            raise ConvertStructWrongSourceTypeError("When using return_unhandled, sources must be dicts, not classes")

        return {k: v for k, v in source_dict.items() if k not in all_srcs}

    return field_specs, unhandled_getter


def _setup_source_dest_finder(destination_type):
    def _get_with_dest_by_reference(mut_dest, source):
        return source, mut_dest

    def _get_with_dest_new_dict(source):
        return source, dict()

    if destination_type in ['class-by-reference', 'dict-by-reference']:
        return _get_with_dest_by_reference
    elif destination_type == 'dict':
        return _get_with_dest_new_dict
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: '{destination_type}'")


def _setup_field_getter(source_type, none_means_missing):
    def _dict_getter(source_dict, field):
        return source_dict.get(field, _NO_VALUE)

    def _class_getter(source_class, field):
        return getattr(source_class, field, _NO_VALUE)

    if source_type == 'dict':
        base_getter = _dict_getter
    elif source_type == 'class':
        base_getter = _class_getter
    else:
        raise ConvertStructCompileError(f"Unsupported source type: '{source_type}'")

    if not none_means_missing:
        return base_getter

    def _adjust_nones(source, field):
        value = base_getter(source, field)
        return value if value is not None else _NO_VALUE

    return _adjust_nones


def _setup_field_setter(destination_type):
    def _dict_setter(dest_dict, field, value):
        dest_dict[field] = value

    def _class_setter(dest_class, field, value):
        setattr(dest_class, field, value)

    if destination_type in ['dict', 'dict-by-reference']:
        return _dict_setter
    elif destination_type == 'class-by-reference':
        return _class_setter
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: '{destination_type}'")


def _setup_result_extractor(source_type, destination_type, return_unparsed_option, unhandled_getter):
    def _return_none(_source, _dest):
        return None

    def _return_unparsed(source, _dest):
        return unhandled_getter(source)

    def _return_dest(_source, dest):
        return dest

    def _return_dest_and_unparsed(source, dest):
        return dest, unhandled_getter(source)

    if source_type == 'class' and return_unparsed_option:
        raise ConvertStructCompileError("return_unparsed cannot be used for sources of type 'class'")

    if destination_type in ['class-by-reference', 'dict-by-reference']:
        return _return_unparsed if return_unparsed_option else _return_none
    elif destination_type == 'dict':
        return _return_dest_and_unparsed if return_unparsed_option else _return_dest
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: '{destination_type}'")


def _setup_conversion_core(fields, source_dest_finder, getter, setter, result_extractor):
    def _convert_core(*args):
        source, destination = source_dest_finder(*args)

        field_getter = lambda field_name: getter(source, field_name)

        for dest_field, field_spec in fields:
            value = field_spec.do_convert(field_getter)

            if value is not _NO_VALUE:
                setter(destination, dest_field, value)

        return result_extractor(source, destination)

    return _convert_core


@dataclass(frozen=True)
class ConvertStructFieldSpec:
    source: str  # Name of field to copy data from
    required: bool = False
    filter: Optional[Callable[[any], bool]] = None
    if_different: Optional[str] = None  # Only copy if it is different to this other field (before conversion)
    convert: Optional[Callable[[any], any]] = None

    def do_convert(self, field_getter):
        value = field_getter(self.source)

        if value is _NO_VALUE:
            if self.required:
                raise ConvertStructMissingRequiredFieldError(self.source)

            return _NO_VALUE

        if (self.filter is not None) and not self.filter(value):
            return _NO_VALUE
        if (self.if_different is not None) and (value == field_getter(self.if_different)):
            return _NO_VALUE

        if self.convert is not None:
            value = self.convert(value)

        return value

    @staticmethod
    def parse(raw_field_spec, default_source):
        if isinstance(raw_field_spec, ConvertStructFieldSpec):
            return raw_field_spec

        normalized_raw_field_spec = _normalize_raw_field_spec(raw_field_spec)

        if 'ignore' in normalized_raw_field_spec:
            if not normalized_raw_field_spec['ignore']:
                raise ConvertStructCompileError("If 'ignore' is set, it must be True")
            if len(normalized_raw_field_spec) > 1:
                raise ConvertStructCompileError("If 'ignore' is set, it must be the only key")

            return None

        if ('store' in raw_field_spec) and ('convert' in raw_field_spec):
            raise ConvertStructCompileError("The 'store' and 'convert' parameters are mutually exclusive")

        init_params = dict(source=default_source)
        filters = []

        # How ironic that the struct converter itself would be excellent at doing the job of the following code!
        # Chicken and the egg...

        for key, value in normalized_raw_field_spec.items():
            try:
                if key == 'src':
                    init_params['source'] = _expect_field_name(value)
                elif key == 'if_different':
                    init_params[key] = _expect_field_name(value)
                elif key == 'req':
                    init_params['required'] = _typecheck(value, bool)
                elif key == 'skip_empty':
                    if _typecheck(value, bool):
                        filters.append((1, _is_nonempty))
                elif key == 'skip_if':
                    filters.append((2, _make_not_eq_filter(value)))
                elif key == 'convert':
                    init_params[key] = _parse_converter(value)
                elif key == 'store':
                    init_params['convert'] = _parse_store(value)
                else:
                    raise KeyError("Don't recognize this field")
            except Exception as e:
                raise ConvertStructCompileError(f"Invalid field spec parameter '{key}'") from e

        if len(filters) > 0:
            init_params['filter'] = lambda x: all(filt(x) for _, filt in sorted(filters, key=lambda pair: pair[0]))

        return ConvertStructFieldSpec(**init_params)


def _normalize_raw_field_spec(raw_field_spec):
    if (raw_field_spec is None) or (raw_field_spec is True):
        return dict()
    if raw_field_spec is False:
        return dict(ignore=True)
    if isinstance(raw_field_spec, Mapping):
        return raw_field_spec
    if isinstance(raw_field_spec, str):
        return {raw_field_spec: True} if raw_field_spec != '' else dict()
    if isinstance(raw_field_spec, Sequence):
        result = dict()

        for part in raw_field_spec:
            for k, v in _normalize_raw_field_spec(part).items():
                if k in result:
                    raise ConvertStructCompileError(f"Parameter '{k}' is specified more than once")
                result[k] = v

        return result

    raise ConvertStructCompileError(f"Can't parse field spec of type {type(raw_field_spec).__name__}")


def _expect_field_name(value):
    if not isinstance(value, str):
        raise TypeError(f"Field name expected, got {type(value).__name__}")
    if str == '':
        raise ValueError("Field name cannot be empty")

    return value


def _typecheck(value, expected_type):
    if not isinstance(value, expected_type):
        raise TypeError(f"Expected {expected_type}, got {type(value).__name__}")

    return value


def _is_nonempty(value):
    return not (
        (value is 0) or (value is False) or (value is None) or (hasattr(value, '__len__') and (len(value) == 0))
    )


def _make_not_eq_filter(value):
    return lambda x: x != value


def _parse_converter(converter_spec):
    _typecheck(converter_spec, (str, Callable))

    if not isinstance(converter_spec, str):
        return converter_spec

    if converter_spec == 'utf8':
        return lambda x: x.decode('utf-8')
    elif converter_spec == 'hex':
        return lambda x: x.hex()

    raise ValueError(f"Unknown built-in converter: '{converter_spec}'")


def _parse_store(value):
    _typecheck(value, Hashable)

    try:
        _ = hash(value)
    except Exception:
        raise TypeError("Only constant (hashable) values may be stored")

    return lambda _: value


class ConvertStructCompileError(Exception):
    """
    Base class for all exceptions related to setting up a struct converter incorrectly.
    """


class ConvertStructRuntimeError(Exception):
    """
    Base class for all exceptions thrown when a struct converter encounters bad data at runtime.
    """


class ConvertStructMissingRequiredFieldError(ConvertStructRuntimeError):
    field = None

    def __init__(self, field):
        super().__init__(f"Missing required field '{field}'")
        self.field = field


class ConvertStructWrongSourceTypeError(ConvertStructRuntimeError):
    pass