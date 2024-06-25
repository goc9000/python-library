from typing import Union, Any

from collections.abc import Mapping, Sequence


RawSourceType = str
RawDestinationType = str

NormalizedRawFieldSpec = Mapping[str, Any]
RawFieldSpec = Union[None, bool, str, NormalizedRawFieldSpec, Sequence['RawFieldSpec']]
RawFieldSpecs = Mapping[str, RawFieldSpec]
