
import sys
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.data.binance_client import BinanceClient
from tezaver.core import coin_cell_paths

# Import download logic
sys.path.insert(0, os.path.dirname(__file__))
from download_spot_data import download_symbol, get_year_range

def main():
    symbol = "AGIXUSDT"
    timeframe = "1d"
    years = [2023, 2024, 2025, 2026]
    
    client = BinanceClient()
    
    print(f"🚀 Force Downloading {symbol} {timeframe} for {years}")
    
    # Check existing
    path = coin_cell_paths.get_history_file(symbol, timeframe)
    existing_df = None
    if path.exists():
        print(f"Loading existing data from {path}")
        existing_df = pd.read_parquet(path)
    
    current_df = existing_df
    
    for year in years:
        start_ms, end_ms = get_year_range(year)
        print(f"  Downloading {year}...")
        
        current_df = download_symbol(client, symbol, timeframe, start_ms, end_ms, current_df)
        
        if current_df is not None:
            print(f"  Total bars so far: {len(current_df)}")
        else:
            print(f"  Warning: No data for {year}")

    if current_df is not None and not current_df.empty:
        path.parent.mkdir(parents=True, exist_ok=True)
        current_df.to_parquet(path, index=False)
        print(f"✅ Saved {len(current_df)} bars to {path}")
    else:
        print("❌ Failed to download data")

if __name__ == "__main__":
    main()
