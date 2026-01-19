"""
ARK False Positive Investigation
================================
Analyzes ARK 2023-10-31 failure.
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
    symbol = 'ARKUSDT'
    dt_str = '2023-10-31'
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    
    sig_dt = pd.to_datetime(dt_str).date()
    row = df_1d[df_1d['datetime'].dt.date == sig_dt].iloc[0]
    idx = row.name
    
    prev_row = df_1d.loc[idx-1]
    prev_prev_row = df_1d.loc[idx-2]
    
    # Also check the successful ARK signals for comparison
    hits = ['2023-10-30', '2023-11-04', '2024-01-25']

    print("="*80)
    print("🔍 ARK FALSE POSITIVE INVESTIGATION")
    print("="*80)
    
    print(f"\nFAIL: {dt_str}")
    print(f"  EMA Dist: {row['ema_dist']:.1f}%")
    print(f"  Daily Ch: {row['daily_ch']:.1f}%")
    print(f"  Prev Day Ch: {prev_row['daily_ch']:.1f}%")
    print(f"  Prev-Prev Day Ch: {prev_prev_row['daily_ch']:.1f}%")
    
    print(f"\nHITS for comparison:")
    for h in hits:
        h_row = df_1d[df_1d['datetime'].dt.date == pd.to_datetime(h).date()].iloc[0]
        h_idx = h_row.name
        h_prev = df_1d.loc[h_idx-1]
        print(f"  {h} | EMA: {h_row['ema_dist']:.1f}% | Daily: {h_row['daily_ch']:.1f}% | Prev: {h_prev['daily_ch']:.1f}%")

if __name__ == "__main__":
    main()
