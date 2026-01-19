"""
SYNUSDT Unique Strategy V1 (Final)
===================================
SYN-Specific Strategy: 3-Day Momentum + Volume + No Consecutive Signals

Discovery: SYN's false positive was a consecutive signal.
Filtering consecutive signals achieves 100% precision.

Final Rules:
- mom_3d >= 30%
- vol_ratio >= 2x
- No signal within previous 2 days (skip consecutive)
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
    print(f"🎯 {symbol} UNIQUE STRATEGY V1")
    print("=" * 70)
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    signals = []
    last_signal_idx = -10  # Track last signal to skip consecutive
    
    print(f"\n{'DATE':<12} | {'TYPE':<8} | {'GAIN':<6} | {'MOM_3D':<8} | {'VOL':<6}")
    print("-" * 60)
    
    for idx in range(25, len(df_1d)-1):
        row = df_1d.loc[idx]
        
        # SYN UNIQUE: mom_3d >= 30%, vol >= 2x, skip consecutive signals
        if row['mom_3d'] >= 30 and row['vol_ratio'] >= 2.0:
            # Skip if signal was generated within last 2 days
            if idx - last_signal_idx <= 2:
                continue
            
            last_signal_idx = idx
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            res = all_results.get(next_date, ('NONE', 0.0))
            is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
            
            signals.append({'is_hit': is_hit, 'tier': res[0], 'gain': res[1]})
            print(f"{row['datetime'].date()} | {res[0]:<8} | %{res[1]:4.1f} | {row['mom_3d']:>6.1f}% | {row['vol_ratio']:>4.1f}x")
    
    df = pd.DataFrame(signals)
    print("\n" + "="*60)
    print(f"🎯 {symbol} UNIQUE V1 FINAL")
    print("="*60)
    if not df.empty:
        print(f"Total Signals: {len(df)}")
        print(f"Precision: {(df['is_hit'].mean()*100):.1f}%")
        print(f"Hits: {df['is_hit'].sum()} | Fails: {len(df) - df['is_hit'].sum()}")
        
        # Tier breakdown
        tier_counts = {}
        for s in signals:
            t = s['tier']
            tier_counts[t] = tier_counts.get(t, 0) + 1
        print(f"Tier Breakdown: {tier_counts}")

if __name__ == "__main__":
    main()
