"""
MDTUSDT Verification (Full Rule)
================================
Rule: mom_5d >= 35 AND vol_ratio >= 2
Hypothesis: This rule is ALREADY 100% precision.
The audit tool failed to parse the 'AND' and only tested mom_5d >= 35 (which had 3 fails).

This script tests the full rule correctly.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'MDTUSDT'
    print(f"🔬 {symbol} FULL RULE VERIFICATION")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    signals = []
    
    print(f"{'DATE':<12} | {'RES':<4} | {'MOM5':<6} | {'VOL':<5}")
    print("-" * 50)
    
    for idx in range(25, len(df)-1):
        row = df.loc[idx]
        
        # FULL RULE
        if row['mom_5d'] >= 35 and row['vol_ratio'] >= 2:
            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            signals.append(is_hit)
            
            res_str = "✅" if is_hit else "❌"
            print(f"{row['datetime'].date()} | {res_str} | {row['mom_5d']:5.1f} | {row['vol_ratio']:4.1f}")

    if signals:
        hits = sum(signals)
        total = len(signals)
        prec = hits / total * 100
        print("\n" + "="*50)
        print(f"Total Signals: {total}")
        print(f"Hits: {hits}")
        print(f"Fails: {total - hits}")
        print(f"Precision: {prec:.1f}%")
        
        if prec == 100:
            print("✅ STRATEGY IS ALREADY PERFECT!")
        else:
            print("❌ STRATEGY NEEDS REPAIR")
    else:
        print("⚠️ No signals found.")

if __name__ == "__main__":
    main()
