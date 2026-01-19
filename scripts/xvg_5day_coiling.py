"""
XVGUSDT 5-Day Coiling Audit (V16 Signals)
==========================================
Analyzes ATR stability in the 5 days before the signal.
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
    hits = ['2023-06-27', '2023-07-02', '2023-10-24', '2024-03-04', '2024-03-09', '2024-03-29', '2024-12-11', '2025-05-12', '2025-07-17', '2025-07-18', '2025-10-01', '2025-11-15', '2025-12-29']
    fails = ['2023-01-29', '2023-06-25', '2023-12-31', '2024-02-16', '2024-07-16', '2024-08-14', '2024-09-09', '2024-11-13', '2024-11-15', '2024-11-18', '2024-12-02', '2025-04-29', '2025-07-13']

    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['atr'] = (df_1d['high'] - df_1d['low']) / df_1d['close'] * 100

    def get_stats(dates):
        scores = []
        for d in dates:
            idx = df_1d[df_1d['datetime'].dt.date == pd.to_datetime(d).date()].index
            if not idx.empty:
                idx = idx[0]
                # Coiling = How many days in the last 5 had decreasing or stable ATR
                prev_5_atr = df_1d.loc[idx-5:idx-1, 'atr']
                # Count days where ATR[i] < ATR[i-1] * 1.1 (Stable or lower)
                stable_days = 0
                for i in range(1, len(prev_5_atr)):
                    if prev_5_atr.iloc[i] < prev_5_atr.iloc[i-1] * 1.05:
                        stable_days += 1
                scores.append(stable_days)
        return scores

    h_scores = get_stats(hits)
    f_scores = get_stats(fails)

    print("="*80)
    print("🌀 5-DAY COILING SCORE: HITS VS FAILS")
    print("="*80)
    print(f"HITS (n={len(h_scores)}): Avg stable days = {np.mean(h_scores):.1f}")
    print(f"FAILS (n={len(f_scores)}): Avg stable days = {np.mean(f_scores):.1f}")
    
    # Discovery
    t_score = 4
    h_passed = len([s for s in h_scores if s >= t_score])
    f_passed = len([s for s in f_scores if s >= t_score])
    if (h_passed + f_passed) > 0:
        precision = h_passed / (h_passed + f_passed) * 100
        print(f"\nIf we set Coiling Score >= {t_score}:")
        print(f"  Precision: {precision:.1f}% | Signals: {h_passed}")

if __name__ == "__main__":
    main()
