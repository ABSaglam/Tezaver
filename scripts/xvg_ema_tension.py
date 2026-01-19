"""
XVGUSDT EMA Tension Audit (V16 Signals)
========================================
Analyzes price distance to EMA9 for V16 signals.
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
    # V16 Signals
    hits = ['2023-06-27', '2023-07-02', '2023-10-24', '2024-03-04', '2024-03-09', '2024-03-29', '2024-12-11', '2025-05-12', '2025-07-17', '2025-07-18', '2025-10-01', '2025-11-15', '2025-12-29']
    fails = ['2023-01-29', '2023-06-25', '2023-12-31', '2024-02-16', '2024-07-16', '2024-08-14', '2024-09-09', '2024-11-13', '2024-11-15', '2024-11-18', '2024-12-02', '2025-04-29', '2025-07-13']

    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100

    def get_stats(dates):
        dists = []
        for d in dates:
            row = df_1d[df_1d['datetime'].dt.date == pd.to_datetime(d).date()]
            if not row.empty:
                dists.append(row.iloc[0]['ema_dist'])
        return dists

    h_dists = get_stats(hits)
    f_dists = get_stats(fails)

    print("="*80)
    print("📈 EMA TENSION: HITS VS FAILS")
    print("="*80)
    print(f"HITS (n={len(h_dists)}):")
    print(f"  Max Dist: {max(h_dists):.1f}% | Avg Dist: {np.mean(h_dists):.1f}%")

    print(f"FAILS (n={len(f_dists)}):")
    print(f"  Max Dist: {max(f_dists):.1f}% | Avg Dist: {np.mean(f_dists):.1f}%")

    # Discovery
    tension_cap = 15.0 # Example cap
    safe_hits = [d for d in h_dists if d < tension_cap]
    safe_fails = [d for d in f_dists if d < tension_cap]
    
    if (len(safe_hits) + len(safe_fails)) > 0:
        precision = len(safe_hits) / (len(safe_hits) + len(safe_fails)) * 100
        print(f"\nIf we set EMA Tension < {tension_cap}%:")
        print(f"  Precision: {precision:.1f}% | Signals: {len(safe_hits)+len(safe_fails)}")

if __name__ == "__main__":
    main()
