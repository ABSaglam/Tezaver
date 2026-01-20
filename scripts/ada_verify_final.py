
"""
ADAUSDT Verification (Rational Supernova)
========================================
Rule: 
  - mom_5d >= 25
  - ema_dist >= 20
  - rsi <= 85
  - mom_7d >= 25
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ADAUSDT'
    print(f"🔬 {symbol} verification")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Indicators
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_dist'] = (df['close'] / df['ema_50'] - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    signals = []
    
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        current_date = row['datetime'].date()
        
        # FINAL RULE
        if (row['mom_5d'] >= 25 and 
            row['ema_dist'] >= 20 and
            row['rsi'] <= 85 and
            row['mom_7d'] >= 25):
            
            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            signals.append(is_hit)
            
            if is_hit:
                 tier = rally_results[next_date][0]
                 print(f"{current_date} | HIT | M5:{row['mom_5d']:.1f}% | M7:{row['mom_7d']:.1f} | R:{row['rsi']:.1f} | {tier}")
            else:
                 print(f"{current_date} | FAIL | M5:{row['mom_5d']:.1f}% | M7:{row['mom_7d']:.1f} | R:{row['rsi']:.1f}")

    if signals:
        hits = sum(signals)
        total = len(signals)
        prec = hits / total * 100
        print(f"Signals: {total} | Hits: {hits} | Precision: {prec:.1f}%")
    else:
        print("No signals")

if __name__ == "__main__":
    main()
