
"""
AGLDUSDT Verification (Trend Box + RSI + Cooldown)
=================================================
Rule: 
  - ema_dist 15-45 
  - mom_5d 15-40 
  - vol_ratio 2.0-4.0 
  - daily_ch 0-15
  - rsi >= 60
  - NO consecutive signals (5 days cooldown)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'AGLDUSDT'
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
    
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    signals = []
    last_signal_date = None
    
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        current_date = row['datetime'].date()
        
        # FINAL RULE
        if (row['ema_dist'] >= 15 and row['ema_dist'] <= 45 and 
            row['mom_5d'] >= 15 and row['mom_5d'] <= 40 and
            row['vol_ratio'] >= 2.0 and row['vol_ratio'] <= 4.0 and
            row['daily_ch'] >= 0 and row['daily_ch'] <= 15 and
            row['rsi'] >= 60):
            
            # Cooldown check (5 days)
            if last_signal_date is not None and (current_date - last_signal_date).days < 5:
                continue

            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            signals.append(is_hit)
            
            # Update last signal date
            last_signal_date = current_date
            
            if is_hit:
                 tier = rally_results[next_date][0]
                 print(f"{current_date} | HIT | M5:{row['mom_5d']:.1f}% | E:{row['ema_dist']:.1f}% | V:{row['vol_ratio']:.1f} | R:{row['rsi']:.1f} | {tier}")
            else:
                 print(f"{current_date} | FAIL | M5:{row['mom_5d']:.1f}% | E:{row['ema_dist']:.1f}% | V:{row['vol_ratio']:.1f} | R:{row['rsi']:.1f}")

    if signals:
        hits = sum(signals)
        total = len(signals)
        prec = hits / total * 100
        print(f"Signals: {total} | Hits: {hits} | Precision: {prec:.1f}%")
    else:
        print("No signals")

if __name__ == "__main__":
    main()
