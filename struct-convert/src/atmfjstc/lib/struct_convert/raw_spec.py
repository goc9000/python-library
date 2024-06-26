from typing import Union, Any, Type

from collections.abc import Mapping, Sequence


RawSourceType = Union[str, Type]
RawDestinationType = Union[str, Type]

NormalizedRawFieldSpec = Mapping[str, Any]
RawFieldSpec = Union[None, bool, str, NormalizedRawFieldSpec, Sequence['RawFieldSpec']]
RawFieldSpecs = Mapping[str, RawFieldSpec]
