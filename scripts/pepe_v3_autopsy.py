"""
PEPEUSDT V3 Failure Autopsy
============================
Deep dive into 2024-03-01 and 2026-01-01.
Checks EMA distance and 4H RSI exhaustion.
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
    fails = ['2024-03-01', '2026-01-01']
    hits = ['2024-03-04', '2024-11-13']
    
    symbol = 'PEPEUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    
    print("="*80)
    print("📊 PEPE V3 AUTOPSY: EMA TENSION & OVEREXTENSION")
    print("="*80)

    def print_stats(dates, label):
        print(f"\n{label} GROUP:")
        for d in dates:
            row = df_1d[df_1d['datetime'].dt.date == pd.to_datetime(d).date()]
            if not row.empty:
                r = row.iloc[0]
                print(f"  {d} | EMA Dist: {r['ema_dist']:.1f}% | Close: {r['close']:.8f}")

    print_stats(hits, "HITS")
    print_stats(fails, "FAILS")

if __name__ == "__main__":
    main()
