# Matrix V2 Replay DataFeed
"""
Replay data feed for wargame simulations.
"""

from pathlib import Path
from typing import Any

from ..core.datafeed import IDataFeed


class ReplayDataFeed(IDataFeed):
    """
    Replay data feed from historical data.
    
    Provides OHLCV data from stored historical bars.
    """
    
    def __init__(self, symbol: str, timeframe: str, data: list[dict]) -> None:
        """
        Initialize replay data feed with bar data.
        
        Args:
            symbol: Trading symbol.
            timeframe: Bar timeframe.
            data: List of OHLCV bar dictionaries.
        """
        self._symbol = symbol
        self._timeframe = timeframe
        self._bars = data
        self._bar_index = 0
    
    @classmethod
    def from_dummy_data(cls, symbol: str, timeframe: str) -> "ReplayDataFeed":
        """
        Create a ReplayDataFeed with dummy/empty data for testing.
        
        In the future, this will load from Parquet/CSV files.
        
        Args:
            symbol: Trading symbol.
            timeframe: Bar timeframe.
            
        Returns:
            ReplayDataFeed instance with dummy bars.
        """
        dummy_bars: list[dict] = [
            {
                "timestamp": f"2024-01-01T{i:02d}:00:00",
                "open": 42000.0 + i * 10,
                "high": 42100.0 + i * 10,
                "low": 41900.0 + i * 10,
                "close": 42050.0 + i * 10,
                "volume": 100.0 + i,
            }
            for i in range(10)
        ]
        return cls(symbol, timeframe, dummy_bars)
    
    @classmethod
    def from_btc_15m_silver_patterns(
        cls,
        base_path: Path | None = None,
    ) -> "ReplayDataFeed":
        """
        Load BTCUSDT 15m rally_patterns_v1.parquet and expose each row
        as a market_snapshot dict compatible with SilverAnalyzer.
        
        Args:
            base_path: Path to parquet file. Defaults to
                       data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet
                       
        Returns:
            ReplayDataFeed with snapshot data.
        """
        import pandas as pd
        
        if base_path is None:
            base_path = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")
        
        if not base_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {base_path}")
        
        df = pd.read_parquet(base_path)
        
        snapshots: list[dict[str, Any]] = []
        
        for _, row in df.iterrows():
            symbol = row.get("symbol", "BTCUSDT")
            timeframe = row.get("timeframe", "15m")
            
            # Timestamp
            ts = row.get("event_time", None)
            if ts is None:
                ts = row.get("timestamp", None)
            
            # Get label fields for PnL calculation
            future_gain = row.get("label_future_max_gain_pct")
            if future_gain is None:
                future_gain = row.get("future_max_gain_pct")
            
            future_drawdown = row.get("label_future_min_drawdown_pct")
            if future_drawdown is None:
                future_drawdown = row.get("feat_pre_peak_drawdown_pct")
            
            bars_to_peak = row.get("label_bars_to_peak")
            if bars_to_peak is None:
                bars_to_peak = row.get("feat_bars_to_peak")
            
            snapshot: dict[str, Any] = {
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": ts,
                # SilverAnalyzer expected keys (map from parquet columns)
                "rsi_15m": row.get("feat_rsi_15m"),
                "volume_rel": row.get("feat_volume_rel_15m"),
                "atr_pct": row.get("feat_atr_pct_15m"),
                "quality_score": row.get("feat_quality_score"),
                # ML features
                "rsi_gap_1d": row.get("feat_rsi_gap_1d"),
                "atr_pct_15m": row.get("feat_atr_pct_15m"),
                "rsi_1h": row.get("feat_rsi_1h"),
                # PnL calculation fields (labels)
                "future_max_gain_pct": future_gain,
                "future_min_drawdown_pct": future_drawdown,
                "future_bars_to_peak": bars_to_peak,
                # Grade labels (for reference)
                "label_is_silver": row.get("label_is_silver", False),
                "label_is_gold": row.get("label_is_gold", False),
                "label_is_diamond": row.get("label_is_diamond", False),
            }
            
            snapshots.append(snapshot)
        
        return cls("BTCUSDT", "15m", snapshots)
    
    @classmethod
    def from_symbol_timeframe_silver_patterns(
        cls,
        symbol: str,
        timeframe: str,
        base_path: Path | None = None,
    ) -> "ReplayDataFeed":
        """
        Generic loader for any symbol's rally_patterns_v1.parquet.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT", "SOLUSDT").
            timeframe: Timeframe (e.g., "15m").
            base_path: Optional custom path to parquet file.
                       Defaults to data/ai_datasets/{symbol}/{timeframe}/rally_patterns_v1.parquet
                       
        Returns:
            ReplayDataFeed with snapshot data.
            
        Raises:
            FileNotFoundError: If parquet file doesn't exist.
        """
        import pandas as pd
        
        if base_path is None:
            base_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/rally_patterns_v1.parquet")
        
        if not base_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {base_path}")
        
        df = pd.read_parquet(base_path)
        
        snapshots: list[dict[str, Any]] = []
        
        for _, row in df.iterrows():
            row_symbol = row.get("symbol", symbol)
            row_timeframe = row.get("timeframe", timeframe)
            
            # Timestamp
            ts = row.get("event_time", None)
            if ts is None:
                ts = row.get("timestamp", None)
            
            # Get label fields for PnL calculation
            future_gain = row.get("label_future_max_gain_pct")
            if future_gain is None:
                future_gain = row.get("future_max_gain_pct")
            
            future_drawdown = row.get("label_future_min_drawdown_pct")
            if future_drawdown is None:
                future_drawdown = row.get("feat_pre_peak_drawdown_pct")
            
            bars_to_peak = row.get("label_bars_to_peak")
            if bars_to_peak is None:
                bars_to_peak = row.get("feat_bars_to_peak")
            
            snapshot: dict[str, Any] = {
                "symbol": row_symbol,
                "timeframe": row_timeframe,
                "timestamp": ts,
                # SilverAnalyzer expected keys (map from parquet columns)
                "rsi_15m": row.get("feat_rsi_15m"),
                "volume_rel": row.get("feat_volume_rel_15m"),
                "atr_pct": row.get("feat_atr_pct_15m"),
                "quality_score": row.get("feat_quality_score"),
                # ML features
                "rsi_gap_1d": row.get("feat_rsi_gap_1d"),
                "atr_pct_15m": row.get("feat_atr_pct_15m"),
                "rsi_1h": row.get("feat_rsi_1h"),
                # PnL calculation fields (labels)
                "future_max_gain_pct": future_gain,
                "future_min_drawdown_pct": future_drawdown,
                "future_bars_to_peak": bars_to_peak,
                # Grade labels (for reference)
                "label_is_silver": row.get("label_is_silver", False),
                "label_is_gold": row.get("label_is_gold", False),
                "label_is_diamond": row.get("label_is_diamond", False),
            }
            
            snapshots.append(snapshot)
        
        return cls(symbol, timeframe, snapshots)
    
    def load_bars(self, bars: list[dict]) -> None:
        """
        Load historical bars for replay.
        
        Args:
            bars: List of OHLCV bar dictionaries.
        """
        self._bars = bars
        self._bar_index = 0
    
    def reset(self) -> None:
        """Reset the bar index to start from beginning."""
        self._bar_index = 0
    
    def has_next(self) -> bool:
        """Check if there are more bars to process."""
        return self._bar_index < len(self._bars)
    
    def next(self) -> dict | None:
        """Get next bar without symbol/timeframe params."""
        return self.get_next_bar(self._symbol, self._timeframe)
    
    def get_next_bar(self, symbol: str, timeframe: str) -> dict | None:
        """
        Get the next bar from historical data.
        
        Args:
            symbol: Trading symbol (uses internal symbol if different).
            timeframe: Bar timeframe (uses internal timeframe if different).
            
        Returns:
            Dictionary with OHLCV data, or None if no more bars.
        """
        if self._bar_index >= len(self._bars):
            return None
        bar = self._bars[self._bar_index]
        self._bar_index += 1
        return bar
    
    @property
    def total_bars(self) -> int:
        """Total number of bars in the feed."""
        return len(self._bars)
    
    @property
    def remaining_bars(self) -> int:
        """Number of remaining bars to process."""
        return len(self._bars) - self._bar_index
