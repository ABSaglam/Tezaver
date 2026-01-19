"""
SYNUSDT Threshold Sweep
=======================
Finds the 100% precision threshold for SYN based on its unique discriminators.
SYN Key: mom_3d has highest separation (1570%)
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
    symbol = 'SYNUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    print("="*80)
    print("🔬 SYNUSDT THRESHOLD SWEEP (mom_3d focus)")
    print("="*80)
    
    # Sweep mom_3d thresholds
    for mom_t in [10, 15, 20, 25, 30]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_3d'] >= mom_t:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                signals.append({'is_hit': is_hit})
        
        df = pd.DataFrame(signals)
        if not df.empty:
            prec = df['is_hit'].mean() * 100
            hits = df['is_hit'].sum()
            print(f"mom_3d >= {mom_t}%: {len(df)} signals, {hits} hits -> {prec:.1f}%")
    
    print("\n--- Combined Filters ---")
    # Test with volume
    for mom_t in [15, 20, 25]:
        for vol_t in [1.5, 2.0, 2.5]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['mom_3d'] >= mom_t and row['vol_ratio'] >= vol_t:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    res = all_results.get(next_date, ('NONE', 0.0))
                    is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append({'is_hit': is_hit})
            
            df = pd.DataFrame(signals)
            if not df.empty and df['is_hit'].mean() >= 0.9:
                prec = df['is_hit'].mean() * 100
                hits = df['is_hit'].sum()
                print(f"mom_3d >= {mom_t}%, vol >= {vol_t}x: {len(df)} signals, {hits} hits -> {prec:.1f}%")

if __name__ == "__main__":
    main()
