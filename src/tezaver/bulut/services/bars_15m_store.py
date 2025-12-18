# Tezaver Bulut - 15m Bars Store Service
"""
In-memory store for 15m closed bars.
Used by scanner for real-time analysis.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict

from tezaver.bulut.schemas.bar_v1 import BarV1


class Bars15mStore:
    """
    In-memory store for 15m bars using deque ring-buffer.
    Keeps last N bars per symbol for analysis.
    """
    
    def __init__(self, max_bars_per_symbol: int = 400):
        self._max_bars = max_bars_per_symbol
        # deque for O(1) append/pop, maxlen handles eviction automatically
        self._bars: Dict[str, deque[BarV1]] = defaultdict(lambda: deque(maxlen=max_bars_per_symbol))
        self._last_update: Dict[str, datetime] = {}
        self._total_bars_count: int = 0
    
    def ingest_bar(self, bar: BarV1) -> None:
        """Ingest a new closed bar."""
        if not bar.is_closed:
            return  # Only store closed bars
            
        symbol = bar.symbol
        
        # Check if actually new (timestamp check)
        existing = self._bars[symbol]
        if existing:
            last_bar = existing[-1]
            if bar.open_ts <= last_bar.open_ts:
                # Update existing or ignore outlier
                if bar.open_ts == last_bar.open_ts:
                    existing[-1] = bar # Replace last
                return

        existing.append(bar)
        self._last_update[symbol] = datetime.now(timezone.utc)
        
        # Recalculate total roughly or track delta
        self._total_bars_count = sum(len(b) for b in self._bars.values())
    
    def get_last_closed(self, symbol: str) -> Optional[BarV1]:
        """Get most recent closed bar for symbol."""
        bars = self._bars.get(symbol)
        return bars[-1] if bars else None
    
    def get_last_n_closed(self, symbol: str, n: int) -> List[BarV1]:
        """Get last N closed bars for symbol."""
        bars = self._bars.get(symbol)
        if not bars:
            return []
        
        # Convert deque slice to list
        # deque doesn't support slicing directly: list(itertools.islice(d, start, end)) or just list(d)[-n:]
        # list conversion is O(N), but N is small (16-400)
        all_bars = list(bars)
        return all_bars[-n:]
    
    def get_status(self) -> dict:
        """Get store status summary."""
        per_symbol_counts = {
            sym: len(self._bars[sym]) 
            for sym in list(self._bars.keys())[:5] # Sample only first 5 to avoid huge JSON
        }
        
        return {
            "symbols_count": len(self._bars),
            "total_bars": self._total_bars_count,
            "max_bars_per_symbol": self._max_bars,
            "sample_counts": per_symbol_counts
        }

    def clear(self) -> None:
        """Clear all data."""
        self._bars.clear()
        self._last_update.clear()
        self._total_bars_count = 0
