"""
PEPEUSDT Failure Autopsy (V1)
==============================
Analyzes the 18 false positives from V1.
Checks Weekly MACD, BB Width, and Volume Acceleration.
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

def calculate_macd_hist(prices):
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal

def main():
    # Signal dates from V1 output
    hits = ['2023-12-04', '2024-03-03', '2024-11-12']
    fails = [
        '2023-06-23', '2023-09-22', '2023-10-21', '2023-10-25', '2023-11-09',
        '2023-12-06', '2024-01-10', '2024-02-14', '2024-04-13', '2024-09-26',
        '2024-11-06', '2024-11-10', '2024-12-31', '2025-05-10', '2026-01-01',
        '2026-01-03', '2026-01-04', '2026-01-05'
    ]

    symbol = 'PEPEUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    
    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['macd_hist'] = calculate_macd_hist(df_1w['close'])
    df_1w['macd_slope'] = df_1w['macd_hist'] - df_1w['macd_hist'].shift(1)

    print("="*80)
    print("📊 PEPEUSDT FAILURES VS HITS: INDICATOR ANALYSIS")
    print("="*80)

    def analyze_list(dates, label):
        print(f"\n{label} GROUP (n={len(dates)}):")
        pos_slope = 0
        avg_vol_ratio = 0
        for d in dates:
            row_1d = df_1d[df_1d['datetime'].dt.date == pd.to_datetime(d).date()]
            if row_1d.empty: continue
            row_1d = row_1d.iloc[0]
            
            w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
            if w_row['macd_slope'] > 0: pos_slope += 1
            
            prev_row = df_1d.loc[row_1d.name-1]
            vr = row_1d['volume'] / prev_row['volume']
            avg_vol_ratio += vr
            
        print(f"  Positive Weekly MACD Slope: {pos_slope} / {len(dates)} ({(pos_slope/len(dates)*100):.1f}%)")
        print(f"  Avg Volume Growth (Day0/Day-1): {(avg_vol_ratio/len(dates)):.1f}x")

    analyze_list(hits, "HITS")
    analyze_list(fails, "FAILS")

if __name__ == "__main__":
    main()
