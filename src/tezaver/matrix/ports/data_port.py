from typing import List, Protocol
from tezaver.matrix.core.bars import Bar

class DataPort(Protocol):
    def get_closed_bars(self, symbol: str, timeframe: str) -> List[Bar]:
        """Fetches a list of closed bars for the given symbol and timeframe.
        Bars should be sorted by timestamp ascending.
        Timestamp unit: Milliseconds (Matrix Internal).
        """
        ...
