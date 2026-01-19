"""
PEPEUSDT Failure vs Hit Analysis
=================================
Compares advanced features (BB Squeeze, Vol Conc) 
between successful hits and false positives.
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

def calculate_bb_width(prices, window=20):
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    return (std * 4) / sma if not (sma == 0).any() else pd.Series(0, index=prices.index)

def main():
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
    df_1d['bb_width'] = calculate_bb_width(df_1d['close'])
    df_1d['bb_width_ma10'] = df_1d['bb_width'].rolling(10).mean()
    df_1d['bb_squeeze'] = df_1d['bb_width'] / df_1d['bb_width_ma10']

    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')

    def get_group_stats(dates):
        results = []
        for d in dates:
            sig_dt = pd.to_datetime(d).date()
            row_1d = df_1d[df_1d['datetime'].dt.date == sig_dt]
            if row_1d.empty: continue
            row_1d = row_1d.iloc[0]
            
            day_bars_1h = df_1h[df_1h['datetime'].dt.date == sig_dt]
            concentration = day_bars_1h['volume'].max() / day_bars_1h['volume'].sum() if not day_bars_1h.empty else 0
            
            results.append({
                'bb_sq': row_1d['bb_squeeze'],
                'vol_conc': concentration
            })
        return pd.DataFrame(results)

    df_h = get_group_stats(hits)
    df_f = get_group_stats(fails)

    print("="*80)
    print("📋 PEPEUSDT HITS VS FAILS: ADVANCED STATS")
    print("="*80)
    
    print("\nHITS Group (n=3):")
    print(df_h.describe().loc[['mean', 'min', 'max']])
    
    print("\nFAILS Group (n=18):")
    print(df_f.describe().loc[['mean', 'min', 'max']])

    print("\n" + "-"*80)
    print("OBSERVATION:")
    # Check if a BB Squeeze filter or Vol Conc filter can separate them
    h_min_sq = df_h['bb_sq'].min()
    h_max_sq = df_h['bb_sq'].max()
    print(f"Hits BB Squeeze Range: {h_min_sq:.2f} - {h_max_sq:.2f}")
    
    f_in_range_sq = df_f[(df_f['bb_sq'] >= h_min_sq) & (df_f['bb_sq'] <= h_max_sq)]
    print(f"Fails in BB Squeeze range: {len(f_in_range_sq)} / {len(df_f)}")

if __name__ == "__main__":
    main()
