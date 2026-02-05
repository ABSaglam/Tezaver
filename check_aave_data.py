import pandas as pd
from pathlib import Path
import sys

DATA_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/AAVEUSDT/data")

def check_dates():
    # Check 1D
    f1d = DATA_DIR / "history_1d.parquet"
    if not f1d.exists():
        print("FAIL: 1D data missing")
        return
        
    df1d = pd.read_parquet(f1d)
    if 'open_time' in df1d.columns:
        dates = pd.to_datetime(df1d['open_time'], unit='ms', utc=True)
    elif 'timestamp' in df1d.columns:
        dates = pd.to_datetime(df1d['timestamp'], unit='ms', utc=True)
    else:
        print("FAIL: 1D data has no time column")
        return
        
    min_date_1d = dates.min()
    print(f"1D Start: {min_date_1d}")
    
    if min_date_1d > pd.Timestamp("2023-01-01", tz='UTC'):
        print(f"FAIL: 1D data starts too late ({min_date_1d.date()} > 2023-01-01)")
        return

    # Check 15M
    f15 = DATA_DIR / "history_15m.parquet"
    if not f15.exists():
        print("FAIL: 15M data missing")
        return
        
    df15 = pd.read_parquet(f15)
    if 'open_time' in df15.columns:
        dates15 = pd.to_datetime(df15['open_time'], unit='ms', utc=True)
    elif 'timestamp' in df15.columns:
        dates15 = pd.to_datetime(df15['timestamp'], unit='ms', utc=True)
    else:
        print("FAIL: 15M data has no time column")
        return
        
    min_date_15 = dates15.min()
    print(f"15M Start: {min_date_15}")
    
    if min_date_15 > pd.Timestamp("2024-01-01", tz='UTC'):
        print(f"FAIL: 15M data starts too late ({min_date_15.date()} > 2024-01-01)")
        return
        
    print("PASS")

if __name__ == "__main__":
    check_dates()
