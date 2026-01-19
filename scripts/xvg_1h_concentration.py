"""
XVGUSDT 1H Spark Concentration Analysis
========================================
Analyzes if hits have more 'concentrated' 1H volume spikes compared to fails.
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

def main():
    # Targets from V7 (Simplified list for analysis)
    # Note: Using the dates from V7 output earlier
    hits = ['2023-05-19', '2023-06-27', '2023-07-02', '2025-10-08', '2025-10-31'] # Signal days for the hits
    fails = ['2023-01-20', '2023-03-12', '2024-11-13', '2026-01-12'] # Sample fails from V7
    
    symbol = 'XVGUSDT'
    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')

    def analyze_day_concentration(sig_day_str):
        sig_day = pd.to_datetime(sig_day_str).date()
        day_bars = df_1h[df_1h['datetime'].dt.date == sig_day]
        if day_bars.empty: return None
        
        total_vol = day_bars['volume'].sum()
        max_1h_vol = day_bars['volume'].max()
        concentration = max_1h_vol / total_vol if total_vol > 0 else 0
        
        # Max hourly volume relative to its own 24h MA
        day_bars['vol_ma'] = day_bars['volume'].rolling(24).mean()
        max_vol_ratio = (day_bars['volume'] / day_bars['vol_ma']).max()
        
        return concentration, max_vol_ratio

    print("="*80)
    print("🔬 1H SPARK CONCENTRATION: HITS VS FAILS")
    print("="*80)
    
    print("\n[HITS]")
    for h in hits:
        stats = analyze_day_concentration(h)
        if stats:
            print(f"  {h}: Concentration={stats[0]:.1%} | Max Vol Ratio={stats[1]:.1f}x")

    print("\n[FAILS]")
    for f in fails:
        stats = analyze_day_concentration(f)
        if stats:
            print(f"  {f}: Concentration={stats[0]:.1%} | Max Vol Ratio={stats[1]:.1f}x")

if __name__ == "__main__":
    main()
