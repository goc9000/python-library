from collections.abc import Set
from typing import Callable, Any, Tuple, Union
from collections.abc import Mapping

from atmfjstc.lib.py_lang_utils.token import Token
from atmfjstc.lib.py_lang_utils.data_objs import get_obj_likely_data_fields_with_defaults

from .spec import ConversionSpec, SourceType, DestinationType, FieldSpec
from .errors import ConvertStructCompileError, ConvertStructMissingRequiredFieldError


_NO_VALUE = Token()


def compile_converter(spec: ConversionSpec) -> Callable:
    unhandled_getter = _setup_unhandled_getter(spec.source_type, spec.fields, spec.ignored_fields)
    source_dest_finder = _setup_source_dest_finder(spec.destination_type)
    getter = _setup_field_getter(spec.source_type, spec.none_means_missing)
    setter = _setup_field_setter(spec.destination_type)
    result_extractor = \
        _setup_result_extractor(spec.source_type, spec.destination_type, spec.return_unparsed, unhandled_getter)

    return _setup_conversion_core(spec.fields, source_dest_finder, getter, setter, result_extractor)


ParsedFieldSpecs = tuple[FieldSpec, ...]
UnhandledGetter = Callable[[Mapping], dict]
SourceDestFinder = Callable[..., Tuple[Any, Any]]
FieldGetter = Callable[[Any, str], Any]
FieldSetter = Callable[[Any, str, Any], None]
ConvertReturnValue = Union[None, dict, Any, Tuple[Any, dict]]
ResultExtractor = Callable[[Any, Any], ConvertReturnValue]


def _setup_unhandled_getter(
    source_type: SourceType, fields: ParsedFieldSpecs, ignored_fields: Set[str]
) -> UnhandledGetter:
    all_srcs = set(field.source for field in fields) | ignored_fields

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
) -> Callable:
    def _convert_core(*args):
        source, destination = source_dest_finder(*args)

        field_getter = lambda field_name: getter(source, field_name)

        for field_spec in fields:
            value = do_convert(field_spec, field_getter)

            if value is not _NO_VALUE:
                setter(destination, field_spec.destination, value)

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
