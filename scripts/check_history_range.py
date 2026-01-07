
import pandas as pd
from pathlib import Path

# BTC
p_btc = Path("coin_cells/BTCUSDT/data/history_15m.parquet")
if p_btc.exists():
    df = pd.read_parquet(p_btc)
    if not df.empty:
        # handle timestamp col
        ts = None
        if 'open_time' in df.columns: ts = pd.to_datetime(df['open_time'], unit='ms')
        elif 'timestamp' in df.columns: ts = pd.to_datetime(df['timestamp']) # might be ms int or datetime
        
        if ts is not None:
            print(f"BTCUSDT 15m Range: {ts.min()} -> {ts.max()} ({len(df)} rows)")
        else:
             print("BTCUSDT: Could not determine timestamp column", df.columns)
    else:
        print("BTCUSDT: Empty parquet")
else:
    print(f"BTCUSDT: File not found at {p_btc}")

# MOG to compare
p_mog = Path("coin_cells/1000000MOGUSDT/data/history_15m.parquet")
if p_mog.exists():
    df = pd.read_parquet(p_mog)
    if 'open_time' in df.columns: ts = pd.to_datetime(df['open_time'], unit='ms')
    elif 'timestamp' in df.columns: ts = pd.to_datetime(df['timestamp'])
    print(f"MOG 15m Range: {ts.min()} -> {ts.max()} ({len(df)} rows)")
else:
    print(f"MOG: File not found at {p_mog}")
