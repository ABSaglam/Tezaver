# Bar Cache
"""
Cache for storing and managing bar data per cell.

Ensures no duplicate timestamps.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
import pandas as pd


class BarCache:
    """
    Per-cell bar cache with deduplication.
    
    Stores bars by cell_key (symbol|timeframe|profile_id).
    Ensures no duplicate timestamps.
    """
    
    def __init__(self, max_bars_per_cell: int = 500):
        self._max_bars = max_bars_per_cell
        self._cache: Dict[str, pd.DataFrame] = {}
        self._last_ts: Dict[str, datetime] = {}
    
    def get_cell_key(self, symbol: str, timeframe: str, profile_id: str = "") -> str:
        """Create cell key."""
        return f"{symbol}|{timeframe}|{profile_id}"
    
    def get_last_ts(self, cell_key: str) -> Optional[datetime]:
        """Get last bar timestamp for cell."""
        return self._last_ts.get(cell_key)
    
    def update(
        self,
        cell_key: str,
        new_bars: pd.DataFrame,
    ) -> int:
        """
        Update cache with new bars.
        
        Returns number of new bars added (after dedup).
        """
        if new_bars.empty:
            return 0
        
        if "ts" not in new_bars.columns:
            raise ValueError("new_bars must have 'ts' column")
        
        # Get existing bars
        existing = self._cache.get(cell_key)
        
        if existing is None or existing.empty:
            # First time - store all
            self._cache[cell_key] = new_bars.tail(self._max_bars).copy()
            if not new_bars.empty:
                self._last_ts[cell_key] = new_bars["ts"].max()
            return len(new_bars)
        
        # Deduplicate by timestamp
        existing_ts = set(existing["ts"].tolist())
        new_only = new_bars[~new_bars["ts"].isin(existing_ts)]
        
        if new_only.empty:
            return 0
        
        # Append and trim
        combined = pd.concat([existing, new_only], ignore_index=True)
        combined = combined.drop_duplicates(subset=["ts"], keep="last")
        combined = combined.sort_values("ts").tail(self._max_bars)
        
        self._cache[cell_key] = combined.reset_index(drop=True)
        self._last_ts[cell_key] = combined["ts"].max()
        
        return len(new_only)
    
    def get_bars(self, cell_key: str) -> Optional[pd.DataFrame]:
        """Get cached bars for cell."""
        return self._cache.get(cell_key)
    
    def has_new_bar(self, cell_key: str, new_bars: pd.DataFrame) -> bool:
        """Check if new_bars contains a bar newer than cache."""
        if new_bars.empty:
            return False
        
        last_ts = self._last_ts.get(cell_key)
        if last_ts is None:
            return True
        
        return new_bars["ts"].max() > last_ts
    
    def get_latest_bar(self, cell_key: str) -> Optional[Dict]:
        """Get latest bar for cell as dict."""
        bars = self._cache.get(cell_key)
        if bars is None or bars.empty:
            return None
        return bars.iloc[-1].to_dict()
    
    def get_stats(self) -> Dict[str, Dict]:
        """Get cache stats."""
        return {
            cell_key: {
                "bar_count": len(df),
                "last_ts": self._last_ts.get(cell_key),
            }
            for cell_key, df in self._cache.items()
        }
