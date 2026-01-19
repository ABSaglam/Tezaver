"""
XVGUSDT 1H Micro-Trend Shape Analysis
======================================
Analyzes the internal 1H structure of V16 signals.
Looking for Higher Highs (HH) vs Double Tops.
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
    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')

    def check_shape(sig_day_str):
        dt = pd.to_datetime(sig_day_str).date()
        # Look at the last 12 hours of the signal day
        bars = df_1h[df_1h['datetime'].dt.date == dt].tail(12)
        if len(bars) < 6: return "Missing"
        
        # Simple HH Check: Is the second half of the day higher than the first half?
        first_half = bars.iloc[:6]['high'].max()
        second_half = bars.iloc[6:]['high'].max()
        
        is_hh = second_half > first_half
        # Momentum: Slope of the 12 bars
        slope = np.polyfit(np.arange(len(bars)), bars['close'].values, 1)[0]
        
        return "HH" if is_hh and slope > 0 else "Fail"

    print("="*80)
    print("📈 1H MICRO-SHAPE: HITS VS FAILS")
    print("="*80)
    
    h_count = 0
    for h in hits:
        shape = check_shape(h)
        if shape == "HH": h_count += 1
    print(f"HITS with HH Shape: {h_count} / {len(hits)} ({h_count/len(hits)*100:.1f}%)")

    f_count = 0
    for f in fails:
        shape = check_shape(f)
        if shape == "HH": f_count += 1
    print(f"FAILS with HH Shape: {f_count} / {len(fails)} ({f_count/len(fails)*100:.1f}%)")

if __name__ == "__main__":
    main()
