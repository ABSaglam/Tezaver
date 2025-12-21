"""
CLOUD-1010: CloudDataFeedPort - Data feed adapter for cloud service.
REPLAY and POLL modes for closed-bar data.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pathlib import Path
import pandas as pd


class DataFeedPort(ABC):
    """Abstract base for data feed adapters."""
    
    @abstractmethod
    def get_next_bar(self) -> Optional[Dict[str, Any]]:
        """Get next closed bar. Returns None when exhausted."""
        pass
    
    @abstractmethod
    def reset(self):
        """Reset to beginning (for replay)."""
        pass


class ReplayDataFeed(DataFeedPort):
    """
    CLOUD-1010: Replay mode - deterministic parquet source.
    Closed-bar only: returns completed bars one at a time.
    """
    
    def __init__(self, symbol: str, tf: str, base_path: str = "coin_cells"):
        self.symbol = symbol
        self.tf = tf
        self.base_path = Path(base_path)
        self.bars: List[Dict] = []
        self.cursor = 0
        self._load_data()
    
    def _load_data(self):
        """Load bars from parquet."""
        file_path = self.base_path / self.symbol / "data" / f"history_{self.tf}.parquet"
        
        if not file_path.exists():
            self.bars = []
            return
        
        df = pd.read_parquet(file_path)
        
        # Detect timestamp column
        ts_col = 'timestamp' if 'timestamp' in df.columns else 'ts'
        
        self.bars = []
        for _, row in df.iterrows():
            ts = row[ts_col]
            if ts < 100000000000:
                ts = int(ts * 1000)
            
            self.bars.append({
                "timestamp": int(ts),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "symbol": self.symbol,
                "tf": self.tf,
                "is_closed": True
            })
        
        # Sort by timestamp
        self.bars.sort(key=lambda x: x["timestamp"])
    
    def get_next_bar(self) -> Optional[Dict[str, Any]]:
        """Get next closed bar."""
        if self.cursor >= len(self.bars):
            return None
        
        bar = self.bars[self.cursor]
        self.cursor += 1
        return bar
    
    def reset(self):
        """Reset cursor to beginning."""
        self.cursor = 0
    
    def get_bar_count(self) -> int:
        """Total bars available."""
        return len(self.bars)


class PollDataFeed(DataFeedPort):
    """
    CLOUD-1010: Poll mode - live polling (stub).
    Will implement actual exchange polling later.
    """
    
    def __init__(self, symbol: str, tf: str):
        self.symbol = symbol
        self.tf = tf
        self._exhausted = False
    
    def get_next_bar(self) -> Optional[Dict[str, Any]]:
        """Stub: would poll exchange for latest closed bar."""
        # In real implementation:
        # 1. Check if current bar is closed
        # 2. If closed, return it and wait for next
        # 3. Use exchange API (Binance klines, etc.)
        return None  # Stub
    
    def reset(self):
        """Not applicable for live polling."""
        pass


def create_data_feed(mode: str, symbol: str, tf: str, **kwargs) -> DataFeedPort:
    """Factory function for data feed creation."""
    if mode.upper() == "REPLAY":
        return ReplayDataFeed(symbol, tf, kwargs.get("base_path", "coin_cells"))
    elif mode.upper() == "POLL":
        return PollDataFeed(symbol, tf)
    else:
        raise ValueError(f"Unknown data feed mode: {mode}")
