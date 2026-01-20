"""
BONKUSDT Verification (Final Rule)
==================================
Rule: mom_7d >= 3 AND vol_ratio >= 4
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'BONKUSDT'
    print(f"🔬 {symbol} verification")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Indicators
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    signals = []
    
    for idx in range(25, len(df)-1):
        row = df.loc[idx]
        
        # FINAL RULE
        if row['mom_7d'] >= 3 and row['vol_ratio'] >= 4:
            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            signals.append(is_hit)
            if is_hit:
                 tier = rally_results[next_date][0]
                 print(f"{row['datetime'].date()} | VOL: {row['vol_ratio']:.1f} | MOM7: {row['mom_7d']:.1f}% | {tier}")

    if signals:
        hits = sum(signals)
        total = len(signals)
        prec = hits / total * 100
        print(f"Signals: {total} | Hits: {hits} | Precision: {prec:.1f}%")
    else:
        print("No signals")

if __name__ == "__main__":
    main()
