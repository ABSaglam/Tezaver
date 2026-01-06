
import sys
import os
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths

def check_file_status(path):
    if path.exists():
        try:
            # Just check if file size > 0 to be fast, or read metadata
            if path.stat().st_size > 0:
                return "✅"
            else:
                return "⚠️ (Empty)"
        except:
            return "❌ (Read Error)"
    return "❌"

def analyze_data():
    print("=" * 100)
    print(f"  DATA AVAILABILITY ANALYSIS ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 100)
    print(f"{'SYMBOL':<15} | {'5m (H)':<7} | {'5m (F)':<7} | {'15m (H)':<7} | {'15m (F)':<7} | {'1h (H)':<7} | {'1h (F)':<7} | {'4h (H)':<7} | {'4h (F)':<7} | {'1d (H)':<7} | {'1d (F)':<7} | {'1w (H)':<7} | {'1w (F)':<7}")
    print("-" * 150)

    summary = {tf: {'hist': 0, 'feat': 0} for tf in ['5m', '15m', '1h', '4h', '1d', '1w']}
    
    for symbol in DEFAULT_COINS:
        row = [f"{symbol:<15}"]
        
        for tf in ['5m', '15m', '1h', '4h', '1d', '1w']:
            # History
            hist_path = coin_cell_paths.get_history_file(symbol, tf)
            hist_status = check_file_status(hist_path)
            row.append(f"{hist_status:<7}")
            if "✅" in hist_status:
                summary[tf]['hist'] += 1
            
            # Features (in data/features_{TF}.parquet)
            feat_path = coin_cell_paths.get_coin_data_dir(symbol) / f"features_{tf}.parquet"
            feat_status = check_file_status(feat_path)
            row.append(f"{feat_status:<7}")
            if "✅" in feat_status:
                summary[tf]['feat'] += 1
                
        print(" | ".join(row))

    print("=" * 150)
    print("  SUMMARY SCALING")
    print("=" * 150)
    print(f"Total Coins: {len(DEFAULT_COINS)}")
    for tf in ['5m', '15m', '1h', '4h', '1d', '1w']:
        print(f"{tf:<5}: History: {summary[tf]['hist']}/{len(DEFAULT_COINS)} | Features: {summary[tf]['feat']}/{len(DEFAULT_COINS)}")
    print("=" * 100)

if __name__ == "__main__":
    analyze_data()
