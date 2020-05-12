from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class NTSecurityID:
    revision: int
    authority: int
    subauthorities: Tuple[int, ...]

    def __str__(self):
        return f"S-{self.revision}-{self.authority}{''.join('-' + str(auth) for auth in self.subauthorities)}"


@dataclass(frozen=True)
class NTGuid:
    group1: int
    group2: int
    group3: int
    group4: int
    group5: int

    def __post_init__(self):
        assert 0 <= self.group1 < (1 << 32)
        assert 0 <= self.group2 < (1 << 16)
        assert 0 <= self.group3 < (1 << 16)
        assert 0 <= self.group4 < (1 << 16)
        assert 0 <= self.group5 < (1 << 48)

    def __str__(self):
        return f"{self.group1:08X}-{self.group2:04X}-{self.group3:04X}-{self.group4:04X}-{self.group5:012X}"
