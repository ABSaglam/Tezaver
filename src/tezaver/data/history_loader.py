"""
Tezaver History Loader (Data Service)
=====================================

Helper module to load historical market data (Parquet) for simulation and analysis.
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from tezaver.core import coin_cell_paths

def load_single_coin_history(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Load history parquet file for a single coin and timeframe.
    
    Args:
        symbol: e.g. 'BTCUSDT'
        timeframe: e.g. '1h'
        
    Returns:
        DataFrame with DateTimeIndex or None if not found.
    """
    try:
        # Construct path: data/history/1h/BTCUSDT.parquet
        file_path = coin_cell_paths.get_history_file(symbol, timeframe)
        
        if not file_path.exists():
            return None
            
        df = pd.read_parquet(file_path)
        
        if not isinstance(df.index, pd.DatetimeIndex):
            # 1. Try 'datetime' column (Tezaver standard)
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
                df.set_index('datetime', inplace=True)
            # 2. Try 'open_time' (Binance raw)
            elif 'open_time' in df.columns:
                df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
                df.set_index('open_time', inplace=True)
            # 3. Try 'timestamp' (Generic)
            elif 'timestamp' in df.columns:
                # Assuming ms timestamp if huge integer
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
        # Sort just in case
        df.sort_index(inplace=True)
        
        return df
        
    except Exception as e:
        print(f"Error loading history for {symbol} {timeframe}: {e}")
        return None
