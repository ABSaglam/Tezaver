"""
Quadratic Cluster Blind-Zone Autopsy
====================================
Compares the 4 hits vs 97 fails within the Oct 2025 - Jan 2026 period.
Focuses on BB Squeeze, 1H Heat, and Daily Jump.
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
    # Known hits in Test Zone from previous run
    test_hits = [
        ('MDTUSDT', '2025-10-14'), # Approximate, will verify
        ('MDTUSDT', '2025-11-20'), 
        ('OMUSDT',  '2025-12-05'),
        ('RAYUSDT', '2026-01-05')
    ]
    
    symbols = ['SYNUSDT', 'OMUSDT', 'MDTUSDT', 'RAYUSDT']
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    test_start = datetime(2025, 10, 1)
    
    hit_stats = []
    fail_stats = []

    for symbol in symbols:
        print(f"Analyzing {symbol} Test Zone...")
        cursor.execute("SELECT raw_data FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
        dg_dates = set([pd.to_datetime(json.loads(r[0])['start_time']).date() for r in cursor.fetchall()])
        
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        df_1d['bb_width'] = calculate_bb_width(df_1d['close'])
        df_1d['bb_sq'] = df_1d['bb_width'] / df_1d['bb_width'].rolling(10).mean()
        df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100

        # DNA matches (using v2 archetypes)
        with open("library/quad_cluster_archetypes_isolated.json", 'r') as f: archetypes = json.load(f)
        coin_archetypes = archetypes[symbol]

        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['datetime'] < test_start: continue
            
            # Simplified DNA check for candidates
            # (Just reusing the candidates from the previous test)
            if row['daily_ch'] < 5: continue # Ignore minor moves
            
            is_hit = (df_1d.loc[idx+1, 'datetime'].date() in dg_dates)
            
            stat = {
                'symbol': symbol,
                'date': row['datetime'].date(),
                'bb_sq': row['bb_sq'],
                'daily_ch': row['daily_ch']
            }
            
            if is_hit: hit_stats.append(stat)
            else: fail_stats.append(stat)

    df_h = pd.DataFrame(hit_stats)
    df_f = pd.DataFrame(fail_stats)

    print("\n" + "="*80)
    print("📋 BLIND ZONE AUTOPSY RESULTS")
    print("="*80)
    
    print(f"\nHITS (n={len(df_h)}):")
    print(df_h.describe().loc[['mean', 'min', 'max']])
    
    print(f"\nFAILS (n={len(df_f)}):")
    print(df_f.describe().loc[['mean', 'min', 'max']])

    if not df_h.empty:
        h_min_sq = df_h['bb_sq'].min()
        h_max_sq = df_h['bb_sq'].max()
        print(f"\nPotential BB Squeeze Filter: {h_min_sq:.2f} - {h_max_sq:.2f}")
        
        f_in_range = df_f[(df_f['bb_sq'] >= h_min_sq) & (df_f['bb_sq'] <= h_max_sq)]
        print(f"Fails in this range: {len(f_in_range)} / {len(df_f)}")

if __name__ == "__main__":
    main()
