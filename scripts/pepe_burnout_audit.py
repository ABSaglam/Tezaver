"""
PEPEUSDT V3 Burnout Analysis
=============================
Checks Daily Gain and Max 4H RSI for V3 signals.
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

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    if (loss == 0).any(): 
        res = pd.Series(50, index=prices.index)
        for i in range(period, len(prices)):
            l = loss.iloc[i]
            if l > 0: res.iloc[i] = 100 - (100 / (1 + gain.iloc[i] / l))
        return res
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def main():
    hits = ['2024-03-04', '2024-11-13']
    fails = ['2024-03-01', '2026-01-01']
    
    symbol = 'PEPEUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['daily_gain'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    
    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    def print_burnout(dates, label):
        print(f"\n{label} GROUP:")
        for d in dates:
            sig_dt = pd.to_datetime(d).date()
            row_1d = df_1d[df_1d['datetime'].dt.date == sig_dt].iloc[0]
            
            day_bars_4h = df_4h[df_4h['datetime'].dt.date == sig_dt]
            max_rsi = day_bars_4h['rsi'].max()
            
            print(f"  {d} | Daily Gain: {row_1d['daily_gain']:.1f}% | Max 4H RSI: {max_rsi:.1f}")

    print("="*80)
    print("🔥 PEPE V3 BURNOUT AUDIT")
    print("="*80)
    print_burnout(hits, "HITS")
    print_burnout(fails, "FAILS")

if __name__ == "__main__":
    main()
