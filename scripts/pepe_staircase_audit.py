"""
PEPEUSDT Volume Staircase Audit
================================
Checks 3-day volume expansion for V3 signals.
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
    hits = ['2024-03-04', '2024-11-13']
    fails = ['2024-03-01', '2026-01-01']
    
    symbol = 'PEPEUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    def print_staircase(dates, label):
        print(f"\n{label} GROUP:")
        for d in dates:
            sig_dt = pd.to_datetime(d).date()
            idx = df_1d[df_1d['datetime'].dt.date == sig_dt].index[0]
            
            v1 = df_1d.loc[idx, 'volume']
            v2 = df_1d.loc[idx-1, 'volume']
            v3 = df_1d.loc[idx-2, 'volume']
            
            g1 = v1 / v2
            g2 = v2 / v3
            
            print(f"  {d} | G1 (0/-1): {g1:.2f}x | G2 (-1/-2): {g2:.2f}x")

    print("="*80)
    print("📊 PEPE V3 VOLUME STAIRCASE AUDIT")
    print("="*80)
    print_staircase(hits, "HITS")
    print_staircase(fails, "FAILS")

if __name__ == "__main__":
    main()
