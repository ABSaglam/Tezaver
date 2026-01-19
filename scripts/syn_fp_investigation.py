"""
SYNUSDT False Positive Investigation
=====================================
Investigates the 1 false positive at mom_3d>=30%, vol>=2x.
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

def main():
    symbol = 'SYNUSDT'
    print(f"🔄 Loading {symbol}...")
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    
    hits = []
    fails = []
    
    print("\n📊 Signals at mom_3d >= 30%, vol >= 2x:")
    print(f"{'DATE':<12} | {'STATUS':<6} | {'mom_3d':<8} | {'daily':<8} | {'vol':<6} | {'ema':<8}")
    print("-" * 60)
    
    for idx in range(25, len(df_1d)-1):
        row = df_1d.loc[idx]
        if row['mom_3d'] >= 30 and row['vol_ratio'] >= 2.0:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            res = all_results.get(next_date, ('NONE', 0.0))
            is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
            status = "HIT" if is_hit else "FAIL"
            
            entry = {
                'date': row['datetime'].date(),
                'mom_3d': row['mom_3d'],
                'daily': row['daily_ch'],
                'vol': row['vol_ratio'],
                'ema': row['ema_dist']
            }
            
            if is_hit: hits.append(entry)
            else: fails.append(entry)
            
            print(f"{row['datetime'].date()} | {status:<6} | {row['mom_3d']:>6.1f}% | {row['daily_ch']:>6.1f}% | {row['vol_ratio']:>4.1f}x | {row['ema_dist']:>6.1f}%")
    
    if fails:
        print("\n🚨 FALSE POSITIVE DETAILS:")
        f_df = pd.DataFrame(fails)
        print(f_df)
        
        h_df = pd.DataFrame(hits)
        print("\n📊 COMPARISON:")
        print(f"Hits avg daily: {h_df['daily'].mean():.1f}%")
        print(f"Fails avg daily: {f_df['daily'].mean():.1f}%")
        print(f"Hits avg ema: {h_df['ema'].mean():.1f}%")
        print(f"Fails avg ema: {f_df['ema'].mean():.1f}%")

if __name__ == "__main__":
    main()
