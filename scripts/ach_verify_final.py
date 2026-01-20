
"""
ACHUSDT Verification (Final Rule)
=================================
Rule: ema_dist >= 30 AND rsi < 90 AND ((mom_5d >= 80) OR (mom_5d >= 39 AND vol_ratio <= 2.2))
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ACHUSDT'
    print(f"🔬 {symbol} verification")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Indicators
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
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
        
        # FINAL RULE
        is_supernova = (row['mom_5d'] >= 80)
        is_grinder = (row['mom_5d'] >= 39) and (row['vol_ratio'] <= 2.2)
        
        if (row['ema_dist'] >= 30 and 
            row['rsi'] < 90 and 
            (is_supernova or is_grinder)):
            
            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            signals.append(is_hit)
            if is_hit:
                 tier = rally_results[next_date][0]
                 type_str = "SUPERNOVA" if is_supernova else "GRINDER"
                 print(f"{row['datetime'].date()} | MOM5: {row['mom_5d']:.1f}% | EMA: {row['ema_dist']:.1f}% | VOL: {row['vol_ratio']:.1f} | {type_str} | {tier}")

    if signals:
        hits = sum(signals)
        total = len(signals)
        prec = hits / total * 100
        print(f"Signals: {total} | Hits: {hits} | Precision: {prec:.1f}%")
    else:
        print("No signals")

if __name__ == "__main__":
    main()
