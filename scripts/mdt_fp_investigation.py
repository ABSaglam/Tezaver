"""
MDTUSDT False Positive Investigation
====================================
Analyzes the 5 false positives to find separator filters.
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
    symbol = 'MDTUSDT'
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    fails = ['2023-07-02', '2024-03-03', '2025-04-10', '2025-05-03', '2025-07-12']
    hits = ['2023-02-04', '2023-02-05', '2023-03-04', '2023-11-24', '2023-11-28', 
            '2024-03-06', '2024-09-21', '2025-03-12', '2025-07-07', '2025-07-24', '2025-08-14', '2025-12-06']
    
    print("="*90)
    print(f"{'DATE':<12} | {'EMA':<8} | {'DAILY':<8} | {'VOL':<6} | {'PREV':<8} | {'STATUS'}")
    print("-" * 90)
    
    fail_stats = []
    hit_stats = []
    
    for dt_str in fails + hits:
        sig_dt = pd.to_datetime(dt_str).date()
        row = df_1d[df_1d['datetime'].dt.date == sig_dt]
        if row.empty: continue
        row = row.iloc[0]
        idx = row.name
        prev_row = df_1d.loc[idx-1]
        status = "FAIL" if dt_str in fails else "HIT"
        
        entry = {
            'ema': row['ema_dist'],
            'daily': row['daily_ch'],
            'vol': row['vol_ratio'],
            'prev': prev_row['daily_ch']
        }
        
        if status == "FAIL": fail_stats.append(entry)
        else: hit_stats.append(entry)
        
        print(f"{dt_str:<12} | {row['ema_dist']:>6.1f}% | {row['daily_ch']:>6.1f}% | {row['vol_ratio']:>4.1f}x | {prev_row['daily_ch']:>6.1f}% | {status}")
    
    hit_df = pd.DataFrame(hit_stats)
    fail_df = pd.DataFrame(fail_stats)
    
    print("\n" + "="*60)
    print("📊 SEPARATOR ANALYSIS")
    print("="*60)
    
    print("\nHITS Statistics:")
    print(hit_df.describe().loc[['mean', 'min', 'max']])
    
    print("\nFAILS Statistics:")
    print(fail_df.describe().loc[['mean', 'min', 'max']])
    
    # Test separators
    print("\n--- POTENTIAL SEPARATORS ---")
    for ema_t in [5, 10, 15]:
        pass_h = len(hit_df[hit_df['ema'] >= ema_t])
        pass_f = len(fail_df[fail_df['ema'] >= ema_t])
        total = pass_h + pass_f
        prec = pass_h / total * 100 if total > 0 else 0
        print(f"EMA >= {ema_t}%: {pass_h} hits, {pass_f} fails -> {prec:.0f}%")
    
    for daily_t in [5, 10, 15]:
        pass_h = len(hit_df[hit_df['daily'] >= daily_t])
        pass_f = len(fail_df[fail_df['daily'] >= daily_t])
        total = pass_h + pass_f
        prec = pass_h / total * 100 if total > 0 else 0
        print(f"Daily >= {daily_t}%: {pass_h} hits, {pass_f} fails -> {prec:.0f}%")

if __name__ == "__main__":
    main()
