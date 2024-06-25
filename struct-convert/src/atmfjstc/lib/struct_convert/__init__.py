from typing import Callable, Any, Iterable, Set, List, Tuple, Union
from collections.abc import Mapping

from atmfjstc.lib.py_lang_utils.token import Token
from atmfjstc.lib.py_lang_utils.data_objs import get_obj_likely_data_fields_with_defaults

from .raw_spec import RawSourceType, RawDestinationType, RawFieldSpecs, RawFieldSpec
from .spec import SourceType, DestinationType, FieldSpec
from .parse_spec import parse_source_type, parse_destination_type, parse_field_spec
from .errors import ConvertStructCompileError, ConvertStructMissingRequiredFieldError


__version__ = '0.0.0'


_NO_VALUE = Token()


StructConverter = Callable


def make_struct_converter(
    source_type: RawSourceType, dest_type: RawDestinationType, fields: RawFieldSpecs,
    return_unparsed: bool = False, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> StructConverter:
    """
    General purpose utility for making functions that convert from a simple structure in dict or object format, to
    another structure in dict or object format, optionally excluding, renaming, converting or checking fields as they
    are accessed.

    The Source and Destination Types
    --------------------------------

    - `source_type` can be one of:

      - ``'dict'``: Any type whose fields can be read with ``obj.get('field_name')``, such as a `dict` or, more
        generally, a `Mapping`.
      - ``'object'``: Any type whose fields can be read with ``obj.field_name``, such as any object with public fields.

        - The aliases ``'obj'`` and ``'class'`` can also be used

    - `destination_type` can be one of:

      - ``'dict'``: The converter will return a new `dict` containing the converted fields.
      - ``'dict-by-reference'``: The converter will receive an existing dict (or `MutableMapping`) and write converted
        fields to it accordingly.

        - The aliases ``'dict-by-ref'``, ``'&dict'`` and ``'@dict'`` can also be used

      - ``'object-by-reference'``: The converter will receive an existing object and set converted fields in it
        accordingly.

        - The aliases ``'obj[ect]-by-ref'``, ``'class-by-ref'``, ``'&obj[ect]'``, ``'@obj[ect]'``, ``'&class'``,  and
          ``'@class'`` can also be used

    Field Specifications
    --------------------

    The `fields` parameter shapes the heart of the conversion algorithm. It is a dict/mapping where the keys are the
    names of the fields that are to be written to the destination, linked to field specification descriptions that
    describe how to obtain the converted value for each field.

    A field specification is normally a dict with one or more of these fields:

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

      - ``'utf8'``: Decodes strings encoded as UTF-8 in a `bytes` value
      - ``'hex'``: Converts a `bytes` value to a hex string

    - `store`: Any value specified here will be stored at the destination regardless of what the value read from the
      source was. Equivalent to a converter that only returns a fixed value. Mutually exclusive with `convert`.

    Alternatively, one can instead provide a dict like ``dict(ignore=True)`` which will cause the field in the source
    with that name to be ignored. This has the same effect as not specifying the field at all, but this affects the
    set of fields that are considered to be 'unparsed' (see the `return_unparsed` options).

    Field Specification Shortcuts
    -----------------------------

    Instead of specifying the full dict-based field descriptor, you can save typing by using these shortcuts when
    appropriate:

    - ``True`` or ``None`` or ``''``: Equivalent to ``dict()`` (a field with all the default options)
    - ``False``: Equivalent to ``dict(ignore=True)``
    - ``'option'``: Equivalent to ``dict(option=True)``. Often used as ``'req'`` to specify fields that are required but
      have no other options.
    - ``(shortcut, shortcut, ...)``: Equivalent to combining the other shortcuts into a single dict. E.g.::

          ('req', 'skip_empty', dict(convert='hex'))

      is equivalent to::

          dict(req=True, skip_empty=True, convert='hex')

    Other Options
    -------------

    - `none_means_missing`: If True (the default), a field is also considered 'missing' (for the purposes of ``req``,
      etc.) if it has a value of None, which is a common convention in classes.

    - `return_unparsed`: If True, the converter will keep track of all the fields in the source that it has no
      instructions on how to parse, and report them alongside the normal result. This is useful for detecting unexpected
      data that one might want to add processing for in the future, or decide to ignore explicitly.

      Note that this only works reliably for mapping-type sources, as classes do not have a standardized way of getting
      a list of all their fields which are intended to represent data. The converter will use a heuristic in this case.

    - `ignore`: A list of additional field names that should be ignored, in addition to those marked as such in the
      `fields`.

    Return Value
    ------------

    The function returns a converter function that can be called like this:

    - For destinations of type ``'dict'``:

      - With `return_unparsed` unset::

            result_dict = convert(source_dict_or_obj)

      - With `return_unparsed` set::

            result_dict, unparsed_fields = convert(source_dict_or_obj)

    - For destinations of type ``'*-by-reference'``:

      - With `return_unparsed` unset::

            convert(dest_dict_or_obj, source_dict_or_obj)

      - With `return_unparsed` set::

            unparsed_fields = convert(dest_dict_or_obj, source_dict_or_obj)

    Exceptions
    ----------

    - All compile-time errors (e.g. wrong setup) cause a `ConvertStructCompileError` to be thrown (possibly chained to
      other underlying exceptions)
    - All runtime errors (bad data) cause a `ConvertStructRuntimeError` subclass to be thrown.
    """

    source_type = parse_source_type(source_type)
    dest_type = parse_destination_type(dest_type)

    field_specs, ignored_fields = _parse_fields(fields)
    unhandled_getter = _setup_unhandled_getter(source_type, field_specs, ignored_fields, ignore)
    source_dest_finder = _setup_source_dest_finder(dest_type)
    getter = _setup_field_getter(source_type, none_means_missing)
    setter = _setup_field_setter(dest_type)
    result_extractor = _setup_result_extractor(source_type, dest_type, return_unparsed, unhandled_getter)

    return _setup_conversion_core(field_specs, source_dest_finder, getter, setter, result_extractor)


ParsedFieldSpecs = List[Tuple[str,'FieldSpec']]
UnhandledGetter = Callable[[Mapping], dict]
SourceDestFinder = Callable[..., Tuple[Any, Any]]
FieldGetter = Callable[[Any, str], Any]
FieldSetter = Callable[[Any, str, Any], None]
ConvertReturnValue = Union[None, dict, Any, Tuple[Any, dict]]
ResultExtractor = Callable[[Any, Any], ConvertReturnValue]


def _parse_fields(fields: RawFieldSpecs) -> Tuple[ParsedFieldSpecs, Set[str]]:
    out_fields = []
    ignored_fields = set()

    for field, raw_field_spec in fields.items():
        try:
            parsed_field_spec = parse_field_spec(raw_field_spec, field)

            if parsed_field_spec is not None:
                out_fields.append((field, parsed_field_spec))
            else:
                ignored_fields.add(field)
        except Exception as e:
            raise ConvertStructCompileError(f"Invalid field spec for field '{field}'") from e

    return out_fields, ignored_fields


def _setup_unhandled_getter(
    source_type: SourceType, fields: ParsedFieldSpecs, ignored_fields: Set[str], ignore_fields_option: Iterable[str]
) -> UnhandledGetter:
    all_srcs = set(field.source for _, field in fields) | set(ignore_fields_option or set()) | ignored_fields

    def _dict_unhandled_getter(source_dict):
        return {k: v for k, v in source_dict.items() if k not in all_srcs}

    def _obj_unhandled_getter(source_obj):
        result = dict()

        for k in get_obj_likely_data_fields_with_defaults(source_obj, include_properties=False).keys():
            if k not in all_srcs:
                try:
                    result[k] = getattr(source_obj, k)
                except Exception:
                    pass

        return result

    if source_type == SourceType.DICT:
        return _dict_unhandled_getter
    elif source_type == SourceType.OBJ:
        return _obj_unhandled_getter
    else:
        raise ConvertStructCompileError(f"Unsupported source type: {source_type}")


def _setup_source_dest_finder(destination_type: DestinationType) -> SourceDestFinder:
    def _get_with_dest_by_reference(mut_dest, source):
        return source, mut_dest

    def _get_with_dest_new_dict(source):
        return source, dict()

    if destination_type in {DestinationType.DICT_BY_REF, DestinationType.OBJ_BY_REF}:
        return _get_with_dest_by_reference
    elif destination_type == DestinationType.DICT:
        return _get_with_dest_new_dict
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_type}")


def _setup_field_getter(source_type: SourceType, none_means_missing: bool) -> FieldGetter:
    def _dict_getter(source_dict, field):
        return source_dict.get(field, _NO_VALUE)

    def _obj_getter(source_obj, field):
        return getattr(source_obj, field, _NO_VALUE)

    if source_type == SourceType.DICT:
        base_getter = _dict_getter
    elif source_type == SourceType.OBJ:
        base_getter = _obj_getter
    else:
        raise ConvertStructCompileError(f"Unsupported source type: {source_type}")

    if not none_means_missing:
        return base_getter

    def _adjust_nones(source, field):
        value = base_getter(source, field)
        return value if value is not None else _NO_VALUE

    return _adjust_nones


def _setup_field_setter(destination_type: DestinationType) -> FieldSetter:
    def _dict_setter(dest_dict, field, value):
        dest_dict[field] = value

    def _obj_setter(dest_obj, field, value):
        setattr(dest_obj, field, value)

    if destination_type in {DestinationType.DICT, DestinationType.DICT_BY_REF}:
        return _dict_setter
    elif destination_type == DestinationType.OBJ_BY_REF:
        return _obj_setter
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_type}")


def _setup_result_extractor(
    source_type: SourceType, destination_type: DestinationType,
    return_unparsed_option: bool, unhandled_getter: UnhandledGetter
) -> ResultExtractor:
    def _return_none(_source, _dest):
        return None

    def _return_unparsed(source, _dest):
        return unhandled_getter(source)

    def _return_dest(_source, dest):
        return dest

    def _return_dest_and_unparsed(source, dest):
        return dest, unhandled_getter(source)

    if destination_type in {DestinationType.DICT_BY_REF, DestinationType.OBJ_BY_REF}:
        return _return_unparsed if return_unparsed_option else _return_none
    elif destination_type == DestinationType.DICT:
        return _return_dest_and_unparsed if return_unparsed_option else _return_dest
    else:
        raise ConvertStructCompileError(f"Unsupported destination type: {destination_type}")


def _setup_conversion_core(
    fields: ParsedFieldSpecs, source_dest_finder: SourceDestFinder, getter: FieldGetter, setter: FieldSetter,
    result_extractor: ResultExtractor
) -> StructConverter:
    def _convert_core(*args):
        source, destination = source_dest_finder(*args)

        field_getter = lambda field_name: getter(source, field_name)

        for dest_field, field_spec in fields:
            value = do_convert(field_spec, field_getter)

            if value is not _NO_VALUE:
                setter(destination, dest_field, value)

        return result_extractor(source, destination)

    return _convert_core


def do_convert(field_spec: FieldSpec, field_getter: Callable[[str], Any]) -> Any:
    value = field_getter(field_spec.source)

    if value is _NO_VALUE:
        if field_spec.required:
            raise ConvertStructMissingRequiredFieldError(field_spec.source)

        return _NO_VALUE

    if (field_spec.filter is not None) and not field_spec.filter(value):
        return _NO_VALUE
    if (field_spec.if_different is not None) and (value == field_getter(field_spec.if_different)):
        return _NO_VALUE

    if field_spec.convert is not None:
        value = field_spec.convert(value)

    return value
