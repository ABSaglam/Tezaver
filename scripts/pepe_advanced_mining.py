"""
PEPEUSDT Advanced Feature Mining
=================================
Analyzes Bollinger Squeeze depth and 1H Volume Concentration 
for all PEPE Diamond/Gold rallies.
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
    symbol = 'PEPEUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
    rallies = cursor.fetchall()
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['bb_width'] = calculate_bb_width(df_1d['close'])
    df_1d['bb_width_ma10'] = df_1d['bb_width'].rolling(10).mean()
    df_1d['bb_squeeze'] = df_1d['bb_width'] / df_1d['bb_width_ma10']

    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')

    print("="*80)
    print("💎 PEPEUSDT ADVANCED FEATURE MINING (22 DIAMONDS + 26 GOLDS)")
    print("="*80)

    stats = []
    for raw_data, tier in rallies:
        raw = json.loads(raw_data)
        start_time = pd.to_datetime(raw['start_time'])
        
        # 1. 1D Bollinger Squeeze on Signal Day (1 day before rally)
        sig_dt = start_time - timedelta(days=1)
        row_1d = df_1d[df_1d['datetime'].dt.date == sig_dt.date()]
        if row_1d.empty: continue
        row_1d = row_1d.iloc[0]
        
        # 2. 1H Volume Concentration on Signal Day
        day_bars_1h = df_1h[df_1h['datetime'].dt.date == sig_dt.date()]
        concentration = 0
        if not day_bars_1h.empty:
            concentration = day_bars_1h['volume'].max() / day_bars_1h['volume'].sum() if day_bars_1h['volume'].sum() > 0 else 0
            
        stats.append({
            'tier': tier,
            'bb_sq': row_1d['bb_squeeze'],
            'vol_conc': concentration
        })

    df_stats = pd.DataFrame(stats)
    print(f"\nAverages for {len(df_stats)} Rallies:")
    print(df_stats.groupby('tier').mean())
    
    print("\nMin/Max for Diamonds:")
    d_stats = df_stats[df_stats['tier'] == 'DIAMOND']
    print(f"  BB Squeeze: {d_stats['bb_sq'].min():.2f} to {d_stats['bb_sq'].max():.2f}")
    print(f"  Vol Conc:   {d_stats['vol_conc'].min():.2f} to {d_stats['vol_conc'].max():.2f}")

if __name__ == "__main__":
    main()
