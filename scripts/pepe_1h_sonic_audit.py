"""
PEPEUSDT 1H Sonic Signature Audit
==================================
Analyzes 1H price/volume pulses for V2 signals.
Compares Hits vs Fails on micro-timeframe.
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
    hits = ['2023-12-04', '2024-02-29', '2024-03-03', '2024-05-22', '2024-11-12']
    fails = [
        '2023-06-23', '2023-10-25', '2023-12-06', '2024-02-14', '2024-03-07',
        '2024-03-08', '2024-09-26', '2024-11-06', '2024-11-10', '2024-12-08',
        '2025-05-10', '2025-11-24', '2026-01-03', '2026-01-04', '2026-01-05'
    ]

    symbol = 'PEPEUSDT'
    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
    df_1h['vol_ma24'] = df_1h['volume'].rolling(24).mean()
    df_1h['price_ch'] = (df_1h['close'] / df_1h['open'] - 1) * 100

    def get_max_pulse(dates):
        data = []
        for d in dates:
            sig_dt = pd.to_datetime(d).date()
            day_bars = df_1h[df_1h['datetime'].dt.date == sig_dt]
            if day_bars.empty: continue
            
            # Find the strongest hour of that day
            max_vol_ratio = (day_bars['volume'] / day_bars['vol_ma24']).max()
            max_price_ch = day_bars['price_ch'].max()
            
            data.append({
                'max_vol_r': max_vol_ratio,
                'max_px_ch': max_price_ch
            })
        return pd.DataFrame(data)

    df_h = get_max_pulse(hits)
    df_f = get_max_pulse(fails)

    print("="*80)
    print("⚡ PEPEUSDT 1H SONIC SIGNATURE: HITS VS FAILS")
    print("="*80)
    
    print("\nHITS Group (n=5):")
    print(df_h.describe().loc[['mean', 'min', 'max']])
    
    print("\nFAILS Group (n=15):")
    print(df_f.describe().loc[['mean', 'min', 'max']])

    print("\n" + "-"*80)
    print("THRESHOLD DISCOVERY:")
    # Can we find a pulse threshold?
    h_min_vol = df_h['max_vol_r'].min()
    h_min_px = df_h['max_px_ch'].min()
    print(f"Hits Min 1H Pulse: Vol={h_min_vol:.1f}x AND Price={h_min_px:.1f}%")
    
    passed_fails = df_f[(df_f['max_vol_r'] >= h_min_vol) & (df_f['max_px_ch'] >= h_min_px)]
    print(f"Fails passing this threshold: {len(passed_fails)} / {len(df_f)}")

if __name__ == "__main__":
    main()
