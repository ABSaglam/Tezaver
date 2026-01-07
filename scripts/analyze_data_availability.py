
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
def analyze_data():
    print("=" * 100)
    print(f"  DATA AVAILABILITY ANALYSIS ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 100)
    print(f"{'SYMBOL':<15} | {'5H':<8} | {'15H':<8} | {'1H H':<8} | {'1H R':<8} | {'4H H':<8} | {'4H R':<8} | {'1D H':<8} | {'1W H':<8}")
    print("-" * 150)
    
    summary = {tf: {'history': 0, 'rally': 0} for tf in ['5m', '15m', '1h', '4h', '1d', '1w']}

    for symbol in DEFAULT_COINS:
        row = [f"{symbol:<15}"]
        
        # 5m History
        h5 = coin_cell_paths.get_history_file(symbol, "5m").exists()
        row.append("✅" if h5 else "❌")
        if h5: summary['5m']['history'] += 1

        # 15m History
        h15 = coin_cell_paths.get_history_file(symbol, "15m").exists()
        row.append("✅" if h15 else "❌")
        if h15: summary['15m']['history'] += 1

        # 1h History & Rally
        h1 = coin_cell_paths.get_history_file(symbol, "1h").exists()
        r1 = coin_cell_paths.get_time_labs_rallies_path(symbol, "1h").exists()
        row.append("✅" if h1 else "❌")
        row.append("✅" if r1 else "❌")
        if h1: summary['1h']['history'] += 1
        if r1: summary['1h']['rally'] += 1

        # 4h History & Rally
        h4 = coin_cell_paths.get_history_file(symbol, "4h").exists()
        r4 = coin_cell_paths.get_time_labs_rallies_path(symbol, "4h").exists()
        row.append("✅" if h4 else "❌")
        row.append("✅" if r4 else "❌")
        if h4: summary['4h']['history'] += 1
        if r4: summary['4h']['rally'] += 1
        
        # 1d History
        h1d = coin_cell_paths.get_history_file(symbol, "1d").exists()
        row.append("✅" if h1d else "❌")
        if h1d: summary['1d']['history'] += 1
        
        # 1w History
        h1w = coin_cell_paths.get_history_file(symbol, "1w").exists()
        row.append("✅" if h1w else "❌")
        if h1w: summary['1w']['history'] += 1

        print(" | ".join(row))

    print("=" * 150)
    print("  SUMMARY SCALING")
    print("=" * 150)
    print(f"Total Coins: {len(DEFAULT_COINS)}")
    
    # Re-print simpler summary
    print(f"5m   : History: {summary['5m']['history']}/{len(DEFAULT_COINS)}")
    print(f"15m  : History: {summary['15m']['history']}/{len(DEFAULT_COINS)}") # Add rally later if needed
    print(f"1h   : History: {summary['1h']['history']}/{len(DEFAULT_COINS)} | Rally: {summary['1h']['rally']}/{len(DEFAULT_COINS)}")
    print(f"4h   : History: {summary['4h']['history']}/{len(DEFAULT_COINS)} | Rally: {summary['4h']['rally']}/{len(DEFAULT_COINS)}")
    print(f"1d   : History: {summary['1d']['history']}/{len(DEFAULT_COINS)}")
    print(f"1w   : History: {summary['1w']['history']}/{len(DEFAULT_COINS)}")
    print("=" * 100)

if __name__ == "__main__":
    analyze_data()
