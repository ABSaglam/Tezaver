
import sys
import os
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

# Add scripts to path for db_helper
sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'AGLDUSDT'
    print(f"🔧 MOMENTUM REFINEMENT: {symbol}")
    print("="*70)

    # 1. Load Data
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # 2. Indicators
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_dist'] = (df['close'] / df['ema_50'] - 1) * 100

    # 3. Apply Base Momentum Rule
    # Base: Mom5 >= 30 AND RSI >= 65
    print("Testing Base Rule: Mom5 >= 30 & RSI >= 65")
    
    hits = []
    fails = []
    
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        
        if (row['mom_5d'] >= 30) and (row['rsi'] >= 65):
            next_date = df.loc[idx+1, 'datetime'].date()
            if next_date in rally_results:
                tier = rally_results[next_date][0]
                hits.append(row)
                print(f"HIT ({tier}) | {row['datetime'].date()} | M5:{row['mom_5d']:.1f} | R:{row['rsi']:.1f} | V:{row['vol_ratio']:.1f} | E:{row['ema_dist']:.1f}")
            else:
                fails.append(row)
                print(f"FAIL       | {row['datetime'].date()} | M5:{row['mom_5d']:.1f} | R:{row['rsi']:.1f} | V:{row['vol_ratio']:.1f} | E:{row['ema_dist']:.1f}")

    # 4. Volume Sweep on this subset
    print("\nVolume Analysis on Base Set:")
    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    if hits_df.empty:
        print("No hits found with base rule.")
        return
        
    for v in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
        h = len(hits_df[hits_df['vol_ratio'] >= v])
        f = len(fails_df[fails_df['vol_ratio'] >= v])
        t = h + f
        if t > 0:
            print(f"Vol >= {v}: {h}/{t} -> {h/t*100:.1f}%")
            
    # 5. EMA Cap Analysis (Maybe too extended?)
    print("\nEMA Cap Analysis:")
    # Check if failures are too extended
    for e in [20, 30, 40, 50, 60]:
        # EMA < e (Not too extended)
        h = len(hits_df[hits_df['ema_dist'] <= e])
        f = len(fails_df[fails_df['ema_dist'] <= e])
        t = h + f
        if t > 0:
            print(f"EMA <= {e}: {h}/{t} -> {h/t*100:.1f}%")
            
    # 6. EMA Floor Analysis (Must be extended?)
    print("\nEMA Floor Analysis:")
    for e in [10, 20, 30]:
        # EMA > e (Must be already trending)
        h = len(hits_df[hits_df['ema_dist'] >= e])
        f = len(fails_df[fails_df['ema_dist'] >= e])
        t = h + f
        if t > 0:
            print(f"EMA >= {e}: {h}/{t} -> {h/t*100:.1f}%")

if __name__ == "__main__":
    main()
