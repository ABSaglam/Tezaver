"""
MDTUSDT Momentum-Based Detector (Unique Strategy)
=================================================
MDT's unique signature: 5-day momentum is the strongest discriminator.
This is MDT-specific and not copied from any other coin.
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
    
    # Get all DG rally dates for validation
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    
    # MDT-specific indicators
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    signals = []
    
    print("="*100)
    print(f"{'DATE':<12} | {'TYPE':<8} | {'GAIN':<6} | {'MOM5D':<8} | {'VOL':<6}")
    print("-" * 100)
    
    # Test various momentum thresholds
    for mom_thresh in [5, 10, 15, 20]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            
            # MDT Unique: 5-day momentum based detection
            if row['mom_5d'] >= mom_thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                signals.append({'is_hit': is_hit, 'mom_5d': row['mom_5d'], 'vol': row['vol_ratio']})
        
        df = pd.DataFrame(signals)
        if not df.empty:
            prec = df['is_hit'].mean() * 100
            hits = df['is_hit'].sum()
            print(f"Mom5D >= {mom_thresh}%: {len(df)} signals, {hits} hits -> {prec:.1f}%")
    
    print("\n" + "="*60)
    print("🔬 TESTING COMBINED FILTERS")
    print("="*60)
    
    # Test combined filters
    for mom_thresh in [10, 15, 20]:
        for vol_thresh in [1.5, 2.0, 2.5]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                
                if row['mom_5d'] >= mom_thresh and row['vol_ratio'] >= vol_thresh:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    res = all_results.get(next_date, ('NONE', 0.0))
                    is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append({'is_hit': is_hit})
            
            df = pd.DataFrame(signals)
            if not df.empty:
                prec = df['is_hit'].mean() * 100
                hits = df['is_hit'].sum()
                if prec >= 80:  # Only show promising results
                    print(f"Mom5D >= {mom_thresh}%, Vol >= {vol_thresh}x: {len(df)} signals, {hits} hits -> {prec:.1f}%")

if __name__ == "__main__":
    main()
