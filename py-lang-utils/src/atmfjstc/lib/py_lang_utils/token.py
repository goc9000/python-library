from typing import Optional


class Token:
    """
    A class for producing tokens, i.e. values that compare equal to nothing else but themselves.

    These tokens can then be used to signal special conditions in a stream of other values.
    """
    _str = None
    _repr = None

    def __init__(self, str_: Optional[str] = None, repr_: Optional[str] = None):
        """
        Produces a new token.

        Args:
            str_: If not None, the text the token should produce when `str()` is called on it
            repr_: If not None, the text the token should produce when `repr()` is called on it
        """
        self._str = str_
        self._repr = repr_

    def __str__(self) -> str:
        return self._str if (self._str is not None) else super().__str__()

    def __repr__(self) -> str:
        return self._repr if (self._repr is not None) else super().__repr__()
