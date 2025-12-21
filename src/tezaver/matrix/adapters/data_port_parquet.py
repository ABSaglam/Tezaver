import pandas as pd
import os
from typing import List
from tezaver.matrix.ports.data_port import DataPort
from tezaver.matrix.core.bars import Bar

class ParquetDataPort(DataPort):
    """
    MXI-1110: Historical Data Adapter for Parquet source (Mac coin_cells).
    TR: Parquet veri kaynağı için (Mac coin_cells) geçmiş veri adaptörü.
    """
    def __init__(self, base_path: str = "coin_cells"):
        self.base_path = base_path

    def get_closed_bars(self, symbol: str, timeframe: str) -> List[Bar]:
        # Path: coin_cells/{SYMBOL}/data/history_{TF}.parquet
        file_path = os.path.join(self.base_path, symbol, "data", f"history_{timeframe}.parquet")
        
        if not os.path.exists(file_path):
            return []
            
        df = pd.read_parquet(file_path)
        
        # Expected columns: ts, open, high, low, close, volume (maybe)
        bars = []
        for _, row in df.iterrows():
            ts = row['timestamp']
            # Normalize to milliseconds
            if ts < 100000000000: # heuristic: epoch seconds
                ts = int(ts * 1000)
            
            # Use int for TS
            ts = int(ts)
            
            bar = Bar(
                ts=ts,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                is_closed=True # Historical parquet source is always closed
            )
            bars.append(bar)
            
        # Ensure deterministic order
        bars.sort(key=lambda x: x.ts)
        return bars
