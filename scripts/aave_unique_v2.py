"""
AAVEUSDT Unique Strategy V2 (Final - Improved)
===============================================
AAVE-Specific Strategy: Severe Dip + Momentum Decline

Discovery: AAVE has UNIQUE reversal pattern - rallies start after declines
Improved from V1 (1 signal) to V2 (2 signals) while maintaining 100%

Rally characteristics:
- Negative daily change (dip)
- Negative 3-day momentum (declining trend)

Final Rules:
- daily_ch <= -15% (severe daily decline)
- mom_3d <= -20% (strong 3-day downtrend)
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
    symbol = 'AAVEUSDT'
    print(f"🎯 {symbol} UNIQUE STRATEGY V2 (DIP-BUYING)")
    print("=" * 70)
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    
    signals = []
    
    print(f"\n{'DATE':<12} | {'TYPE':<8} | {'GAIN':<6} | {'DAILY':<8} | {'MOM_3D':<8}")
    print("-" * 65)
    
    for idx in range(25, len(df_1d)-1):
        row = df_1d.loc[idx]
        
        # AAVE UNIQUE V2: daily <= -15% AND mom_3d <= -20%
        if row['daily_ch'] <= -15 and row['mom_3d'] <= -20:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            res = all_results.get(next_date, ('NONE', 0.0))
            is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
            
            signals.append({'is_hit': is_hit, 'tier': res[0], 'gain': res[1]})
            print(f"{row['datetime'].date()} | {res[0]:<8} | %{res[1]:4.1f} | {row['daily_ch']:>6.1f}% | {row['mom_3d']:>6.1f}%")
    
    df = pd.DataFrame(signals)
    print("\n" + "="*60)
    print(f"🎯 {symbol} UNIQUE V2 FINAL")
    print("="*60)
    if not df.empty:
        print(f"Total Signals: {len(df)}")
        print(f"Precision: {(df['is_hit'].mean()*100):.1f}%")
        print(f"Hits: {df['is_hit'].sum()} | Fails: {len(df) - df['is_hit'].sum()}")
        
        tier_counts = {}
        for s in signals:
            t = s['tier']
            tier_counts[t] = tier_counts.get(t, 0) + 1
        print(f"Tier Breakdown: {tier_counts}")
    else:
        print("⚠️ No signals found")

if __name__ == "__main__":
    main()
