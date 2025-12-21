import pandas as pd
import os
from typing import List, Dict, Optional, Any
from tezaver.matrix.ports.data_port import DataPort
from tezaver.matrix.core.bars import Bar


class DataPortError(Exception):
    """MX-2000.3: Error class for data port issues."""
    def __init__(self, message: str, error_kind: str = "DATA_PORT_ERROR"):
        super().__init__(message)
        self.error_kind = error_kind


class ParquetDataPort(DataPort):
    """
    MXI-1110 + MX-2000.3: Historical Data Adapter for Parquet source (Mac coin_cells).
    Supports both init styles:
      - ParquetDataPort(base_path) + get_closed_bars(symbol, tf)
      - ParquetDataPort(symbol, tf) + get_bars()
    """
    def __init__(self, symbol_or_base_path: str = "coin_cells", timeframe: str = None):
        # Detect init style
        if timeframe is not None:
            # Style 2: ParquetDataPort(symbol, tf)
            self.symbol = symbol_or_base_path
            self.timeframe = timeframe
            self.base_path = "coin_cells"
            self._single_symbol_mode = True
        else:
            # Style 1: ParquetDataPort(base_path)
            self.base_path = symbol_or_base_path
            self.symbol = None
            self.timeframe = None
            self._single_symbol_mode = False

    def get_bars(self, limit: int = None) -> List[Dict[str, Any]]:
        """MX-2000.3: Get bars for single-symbol mode (used by WarEngine)."""
        if not self._single_symbol_mode:
            raise DataPortError("get_bars() requires symbol and tf in constructor", "INVALID_MODE")
        
        bars = self.get_closed_bars(self.symbol, self.timeframe)
        
        if limit:
            bars = bars[:limit]
        
        # Convert to dict format for war_engine compatibility
        return [
            {
                "timestamp": b.ts,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close
            }
            for b in bars
        ]

    def get_closed_bars(self, symbol: str, timeframe: str) -> List[Bar]:
        """Get closed bars from parquet file."""
        # Path: coin_cells/{SYMBOL}/data/history_{TF}.parquet
        file_path = os.path.join(self.base_path, symbol, "data", f"history_{timeframe}.parquet")
        
        # MX-2000.3: Preflight check
        if not os.path.exists(file_path):
            # Return empty list instead of exception
            return []
            
        try:
            df = pd.read_parquet(file_path)
        except Exception as e:
            raise DataPortError(f"Failed to read parquet: {e}", "PARQUET_READ_ERROR")
        
        # Column validation
        required_cols = {'open', 'high', 'low', 'close'}
        actual_cols = set(df.columns)
        if not required_cols.issubset(actual_cols):
            missing = required_cols - actual_cols
            raise DataPortError(f"Missing columns: {missing}", "MISSING_COLUMNS")
        
        # Timestamp column detection
        ts_col = 'timestamp' if 'timestamp' in df.columns else 'ts' if 'ts' in df.columns else None
        if ts_col is None:
            raise DataPortError("No timestamp/ts column found", "MISSING_TIMESTAMP")
        
        bars = []
        for _, row in df.iterrows():
            ts = row[ts_col]
            # Normalize to milliseconds
            if ts < 100000000000:  # heuristic: epoch seconds
                ts = int(ts * 1000)
            
            ts = int(ts)
            
            bar = Bar(
                ts=ts,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                is_closed=True
            )
            bars.append(bar)
            
        # Ensure deterministic order
        bars.sort(key=lambda x: x.ts)
        return bars
