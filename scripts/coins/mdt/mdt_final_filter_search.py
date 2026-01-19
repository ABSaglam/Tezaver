"""
MDTUSDT Final Filter Search
===========================
Finds additional filters to eliminate the 5 false positives.
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
    symbol = 'MDTUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    
    hits = []
    fails = []
    
    for idx in range(25, len(df_1d)-1):
        row = df_1d.loc[idx]
        prev_row = df_1d.loc[idx-1]
        
        # Base filter: Mom5D >= 20%, Vol >= 2x
        if row['mom_5d'] >= 20.0 and row['vol_ratio'] >= 2.0:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            res = all_results.get(next_date, ('NONE', 0.0))
            is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
            
            entry = {
                'date': row['datetime'].date(),
                'mom_5d': row['mom_5d'],
                'vol': row['vol_ratio'],
                'daily': row['daily_ch'],
                'ema': row['ema_dist'],
                'prev_ch': prev_row['daily_ch']
            }
            
            if is_hit: hits.append(entry)
            else: fails.append(entry)
    
    hit_df = pd.DataFrame(hits)
    fail_df = pd.DataFrame(fails)
    
    print("="*80)
    print(f"📊 MDT FALSE POSITIVE ANALYSIS (82.8% Base)")
    print(f"Hits: {len(hit_df)} | Fails: {len(fail_df)}")
    print("="*80)
    
    print("\nHITS:")
    print(hit_df.describe().loc[['mean', 'min', 'max']])
    
    print("\nFAILS:")
    print(fail_df)
    
    # Test additional filters
    print("\n" + "="*60)
    print("🔬 TESTING ADDITIONAL FILTERS")
    print("="*60)
    
    for mom_t in [25, 30, 35]:
        h = len(hit_df[hit_df['mom_5d'] >= mom_t])
        f = len(fail_df[fail_df['mom_5d'] >= mom_t])
        total = h + f
        prec = h / total * 100 if total > 0 else 0
        print(f"Mom5D >= {mom_t}%: {h} hits, {f} fails -> {prec:.0f}%")
    
    for vol_t in [3.0, 4.0, 5.0]:
        h = len(hit_df[hit_df['vol'] >= vol_t])
        f = len(fail_df[fail_df['vol'] >= vol_t])
        total = h + f
        prec = h / total * 100 if total > 0 else 0
        print(f"Vol >= {vol_t}x: {h} hits, {f} fails -> {prec:.0f}%")
    
    for daily_t in [10, 15, 20]:
        h = len(hit_df[hit_df['daily'] >= daily_t])
        f = len(fail_df[fail_df['daily'] >= daily_t])
        total = h + f
        prec = h / total * 100 if total > 0 else 0
        print(f"Daily >= {daily_t}%: {h} hits, {f} fails -> {prec:.0f}%")

if __name__ == "__main__":
    main()
