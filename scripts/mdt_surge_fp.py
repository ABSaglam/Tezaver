"""
MDT SURGE False Positive Investigation
======================================
Investigates the 2 MDT failures in SURGE path.
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
    symbol = 'MDTUSDT'
    
    # MDT signals from V8 output
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    # Known MDT signals from V8 (need to identify which are fails)
    # Based on V8 output: MDT has 11 signals, 9 hits, 2 fails
    # The NONE entries are the fails
    fails = ['2023-02-07', '2025-07-21']  # NONE entries from output
    hits = ['2023-02-04', '2023-02-05', '2023-11-24', '2024-03-06', '2025-03-12', '2025-07-24', '2025-12-06']
    
    print("="*80)
    print("🔍 MDT SURGE FALSE POSITIVE INVESTIGATION")
    print("="*80)
    
    print(f"\n{'DATE':<12} | {'EMA':<8} | {'DAILY':<8} | {'VOL':<6} | {'STATUS'}")
    print("-" * 60)
    
    for dt_str in fails + hits:
        sig_dt = pd.to_datetime(dt_str).date()
        row = df_1d[df_1d['datetime'].dt.date == sig_dt]
        if row.empty: continue
        row = row.iloc[0]
        status = "FAIL" if dt_str in fails else "HIT"
        print(f"{dt_str:<12} | {row['ema_dist']:>6.1f}% | {row['daily_ch']:>6.1f}% | {row['vol_ratio']:>4.1f}x | {status}")

if __name__ == "__main__":
    main()
