from collections.abc import Mapping, MutableMapping
from typing import Callable, Iterable, TypeVar, Type

from .raw_spec import RawSourceType, RawDestinationType, RawFieldSpecs
from .parse_spec import parse_conversion_spec
from .compile import compile_converter, debug_compile_converter


__version__ = '1.2.0'


StructConverter = Callable


def make_struct_converter(
    source_type: RawSourceType, dest_type: RawDestinationType, fields: RawFieldSpecs, ignore: Iterable[str] = (),
    return_unparsed: bool = False, none_means_missing: bool = True, dest_by_reference: bool = False
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
      - (class name): Behaves like ``'object'``, and also checks that the source object is of that specific class

    - `destination_type` can be one of:

      - ``'dict'``: The converter will return a new `dict` containing the converted fields.
      - (class name): The converted will return a new object of this class, initialized with the converted fields.
        Particularly useful for dataclasses.
      - ``'dict-by-reference'``: The converter will receive an existing dict (or `MutableMapping`) and write converted
        fields to it accordingly.
      - ``'object-by-reference'``: The converter will receive an existing object and set converted fields in it
        accordingly.
      - (class name) with `dest_by_reference=` set to ``True``: Like ``object-by-reference``, and also checks that the
        destination object is of that specific class.

    - The following aliases can also be used for specifying the above:

      - dict source: ``dict`` (the class itself instead of the ``'dict'`` text. Note that a subclass will not do)
      - object source: ``'obj'``, ``object`` (the type), ``'class'``
      - dict destination: ``dict`` (the type)
      - dict-by-reference destination: ``'dict-by-ref'``, ``'&dict'``, ``'@dict'``
      - object-by-reference destination: ``'obj[ect]-by-ref'``, ``'class-by-ref'``, ``'&obj[ect]'``, ``'@obj[ect]'``,
          ``'&class'``, ``'@class'``


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
    - `skip_if`: The field will be skipped if it is equal to this value. A list or set of values can also be provided
      (but not a tuple or frozenset, which will be considered one value).
    - `if_different`: Specifies a field in the source to which this field will be compared. It will be skipped unless
      it is different. Useful for backing up values.
    - `convert`: Specifies a function that will be called to convert this field's value before writing it to the
      destination. Applies only if the field is not skipped, and only after the previous tests.

      You can also specify the following strings that refer to built-in converters:

      - ``'utf8'``: Decodes strings encoded as UTF-8 in a `bytes` value
      - ``'hex'``: Converts a `bytes` value to a hex string

    - `store`: Any value specified here will be stored at the destination regardless of what the value read from the
      source was. The value will only be written if the field was not skipped.

      The value can be specified either as a constant value, or as a class or callable (which will be called with no
      parameters to produce a value).

      Mutually exclusive with `convert`.
    - `default`: Any value specified here will be stored at the destination if the source field was not present or
      if it was skipped for any reason.

      The value can be specified either as a constant value, or as a class or callable (which will be called with no
      parameters to produce a value).

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

    spec = parse_conversion_spec(
        source_type, dest_type, fields,
        ignore=ignore,
        return_unparsed=return_unparsed,
        none_means_missing=none_means_missing,
        dest_by_reference=dest_by_reference,
    )

    return compile_converter(spec)


def debug_make_struct_converter(
    source_type: RawSourceType, dest_type: RawDestinationType, fields: RawFieldSpecs, ignore: Iterable[str] = (),
    return_unparsed: bool = False, none_means_missing: bool = True, dest_by_reference: bool = False
) -> dict:
    """
    Debug version of `make_struct_converter` that just returns the code that would have been compiled.
    """

    spec = parse_conversion_spec(
        source_type, dest_type, fields,
        ignore=ignore,
        return_unparsed=return_unparsed,
        none_means_missing=none_means_missing,
        dest_by_reference=dest_by_reference,
    )

    return debug_compile_converter(spec)


T = TypeVar('T')
U = TypeVar('U')


def make_dict_to_dict_converter(
    fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[Mapping], dict]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        'dict', 'dict',
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_dict_to_dict_converter_with_unhandled(
    fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[Mapping], tuple[dict, dict]]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        'dict', 'dict', return_unparsed=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_dict_to_dict_by_ref_converter(
    fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[MutableMapping, Mapping], None]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        'dict', '&dict',
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_dict_to_dict_by_ref_converter_with_unhandled(
    fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[MutableMapping, Mapping], dict]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        'dict', '&dict', return_unparsed=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_dict_to_class_converter(
    dest_class: Type[T], fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[Mapping], T]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        'dict', dest_class,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_dict_to_class_converter_with_unhandled(
    dest_class: Type[T], fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[Mapping], tuple[T, dict]]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        'dict', dest_class, return_unparsed=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_dict_to_class_by_ref_converter(
    dest_class: Type[T], fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[T, Mapping], None]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        'dict', dest_class, dest_by_reference=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_dict_to_class_by_ref_converter_with_unhandled(
    dest_class: Type[T], fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[T, Mapping], dict]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        'dict', dest_class, dest_by_reference=True, return_unparsed=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_class_to_dict_converter(
    source_class: Type[T], fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[T], dict]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        source_class, 'dict',
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_class_to_dict_converter_with_unhandled(
    source_class: Type[T], fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[T], tuple[dict, dict]]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        source_class, 'dict', return_unparsed=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_class_to_dict_by_ref_converter(
    source_class: Type[T], fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[MutableMapping, T], None]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        source_class, '&dict',
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_class_to_dict_by_ref_converter_with_unhandled(
    source_class: Type[T], fields: RawFieldSpecs, ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[MutableMapping, T], dict]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        source_class, '&dict', return_unparsed=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_class_to_class_converter(
    source_class: Type[T], dest_class: Type[U], fields: RawFieldSpecs,
    ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[T], U]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        source_class, dest_class,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_class_to_class_converter_with_unhandled(
    source_class: Type[T], dest_class: Type[U], fields: RawFieldSpecs,
    ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[T], tuple[U, dict]]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        source_class, dest_class, return_unparsed=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_class_to_class_by_ref_converter(
    source_class: Type[T], dest_class: Type[U], fields: RawFieldSpecs,
    ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[U, T], None]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        source_class, dest_class, dest_by_reference=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )


def make_class_to_class_by_ref_converter_with_unhandled(
    source_class: Type[T], dest_class: Type[U], fields: RawFieldSpecs,
    ignore: Iterable[str] = (), none_means_missing: bool = True
) -> Callable[[U, T], dict]:
    """
    Shortcut for `make_struct_converter` with more precise typing.
    """
    return make_struct_converter(
        source_class, dest_class, dest_by_reference=True, return_unparsed=True,
        fields=fields, ignore=ignore, none_means_missing=none_means_missing
    )
