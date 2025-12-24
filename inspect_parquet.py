
import pandas as pd
from datetime import datetime

try:
    path = "coin_cells/BTCUSDT/data/history_15m.parquet"
    df = pd.read_parquet(path)
    print("Columns:", df.columns.tolist())
    print("Rows:", len(df))
    print("Start Date:", df.index.min() if isinstance(df.index, pd.DatetimeIndex) else df.iloc[0]['timestamp'] if 'timestamp' in df.columns else "Unknown")
    print("End Date:", df.index.max() if isinstance(df.index, pd.DatetimeIndex) else df.iloc[-1]['timestamp'] if 'timestamp' in df.columns else "Unknown")
    
    # Check if index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        print("Index is NOT DatetimeIndex")
        if 'timestamp' in df.columns:
             print("Timestamp column sample:", df['timestamp'].head())
    
except Exception as e:
    print(f"Error: {e}")
