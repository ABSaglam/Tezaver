from typing import Any, List, Sequence

class LookaheadViolation(Exception):
    """Raised when code attempts to access future data in a protected sequence."""
    pass

class LookaheadProtectedList:
    """
    MX-5100: A sequence wrapper that prevents lookahead bias.
    Tr: Lookahead bias'ı engelleyen liste sarmalayıcı.
    
    It maintains a 'current_index' and only allows access to elements 
    at or below this index.
    """
    def __init__(self, data: Sequence[Any], initial_index: int = 0):
        self._data = data
        self._current_index = initial_index

    def set_current_index(self, index: int):
        """Advance the visible horizon."""
        self._current_index = index

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            if key > self._current_index:
                raise LookaheadViolation(
                    f"LOOKAHEAD_VIOLATION: Attempted to access index {key} "
                    f"beyond current horizon {self._current_index}"
                )
            return self._data[key]
        elif isinstance(key, slice):
            # For slices, we must ensure stop index is protected
            stop = key.stop if key.stop is not None else len(self._data)
            if stop > self._current_index + 1:
                raise LookaheadViolation(
                    f"LOOKAHEAD_VIOLATION: Slice {key} exposes future data "
                    f"beyond current horizon {self._current_index}"
                )
            return self._data[key]
        else:
            raise TypeError(f"Invalid argument type: {type(key)}")

    def __len__(self) -> int:
        # We only expose length up to current_index + 1
        return min(self._current_index + 1, len(self._data))

    def __iter__(self):
        for i in range(len(self)):
            yield self._data[i]
