"""
Quad Cluster Failure Autopsy (Train Period)
===========================================
Analyzes the 2 failures from the Train period in quad_perfect_detector_v1.
Goal: Find the separator for 100% precision.
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
    fails = [
        ('SYNUSDT', '2025-04-17'),
        ('MDTUSDT', '2025-07-12')
    ]
    hit = ('OMUSDT', '2024-03-04')
    
    all_cases = [hit] + fails
    
    print("="*80)
    print(f"{'SYM':<10} | {'DATE':<12} | {'EMA_DIST':<10} | {'1H_MAX_VOL_R':<12} | {'STATUS'}")
    print("-" * 80)

    for symbol, dt_str in all_cases:
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
        df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
        
        df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
        df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
        df_1h['vol_ma24'] = df_1h['volume'].rolling(24).mean()
        
        sig_dt = pd.to_datetime(dt_str).date()
        row_1d = df_1d[df_1d['datetime'].dt.date == sig_dt].iloc[0]
        
        day_bars_1h = df_1h[df_1h['datetime'].dt.date == sig_dt]
        max_vol_r = (day_bars_1h['volume'] / day_bars_1h['vol_ma24']).max()
        
        status = "HIT" if (symbol, dt_str) == hit else "FAIL"
        print(f"{symbol:<10} | {dt_str:<12} | {row_1d['ema_dist']:>8.1f}% | {max_vol_r:>11.1f}x | {status}")

if __name__ == "__main__":
    main()
