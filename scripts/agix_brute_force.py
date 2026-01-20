
import sys
import os
import pandas as pd
import numpy as np
import itertools

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

# Add scripts to path for db_helper
sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'AGIXUSDT'
    print(f"🔨 BRUTE FORCE ANALYSIS: {symbol}")
    
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
    
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_dist'] = (df['close'] / df['ema_50'] - 1) * 100
    
    # Pinbar / Shadow Logic
    # Lower Shadow = min(open, close) - low
    # Body = abs(close - open)
    # Range = high - low
    # Ratio = Lower Shadow / Range
    df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
    df['range'] = df['high'] - df['low']
    df['shadow_ratio'] = df['lower_shadow'] / df['range']
    
    # Define Target
    df['is_rally'] = False
    for idx in range(len(df)-1):
        next_date = df.loc[idx+1, 'datetime'].date()
        if next_date in rally_results:
            df.loc[idx, 'is_rally'] = True
            
    # Remove NaN
    df = df.dropna().reset_index(drop=True)
    
    total_rallies = df['is_rally'].sum()
    print(f"Total Rallies in Dataset: {total_rallies}")
    
    # SWEEP 1: DIP FOCUS
    print("\n--- DIP SWEEP (Mom <= X) ---")
    param_grid = list(itertools.product(
        [-5, -10, -15],      # mom_max
        [25, 30, 35, 40],    # rsi_max
        [0.0, 0.2, 0.3, 0.4],# shadow_min (Wait for bounce)
        [1.0, 2.0, 100]      # vol_max
    ))
    
    best_prec = 0
    
    for m_max, r_max, s_min, v_max in param_grid:
         mask = (
             (df['mom_5d'] <= m_max) & 
             (df['rsi'] <= r_max) & 
             (df['shadow_ratio'] >= s_min) &
             (df['vol_ratio'] <= v_max)
         )
         hits = df[mask & df['is_rally']]
         fails = df[mask & ~df['is_rally']]
         
         h = len(hits)
         f = len(fails)
         t = h+f
         
         if t >= 2: # Relaxed to 2
             prec = h/t*100
             if prec >= 50:
                 print(f"DIP: M<={m_max} R<={r_max} S>={s_min} V<={v_max} -> {h}/{t} ({prec:.1f}%)")
                 
    # FORENSICS: PINBAR AT 20 (R 20-26)
    print("\n--- FORENSICS: PINBAR AT 20 (M<=-10, 20<=R<=26, S>=0.25) ---")
    mask_pin20 = (
        (df['mom_5d'] <= -10) & 
        (df['rsi'] >= 20) & (df['rsi'] <= 26) & 
        (df['shadow_ratio'] >= 0.25)
    )
    
    hits = df[mask_pin20 & df['is_rally']]
    fails = df[mask_pin20 & ~df['is_rally']]
    
    print("HITS:")
    for _, r in hits.iterrows():
        print(f"  {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | S:{r['shadow_ratio']:.2f}")
    print("FAILS:")
    for _, r in fails.iterrows():
        print(f"  {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | S:{r['shadow_ratio']:.2f}")

    # SWEEP 2: MODERATE DIP (RSI 30-40)
    print("\n--- MODERATE DIP SWEEP (RSI 30-40) ---")
    # Rule: Mom <= -5, 30 <= RSI <= 40
    # Sweeping Vol and Shadow
    param_grid_mod = list(itertools.product(
        [-5, -10],           # mom_max
        [36, 40],            # rsi_max (min 30 implied)
        [0.0, 0.1, 0.2],     # shadow_min
        [0.5, 0.8, 1.5, 100] # vol_max
    ))
    
    for m_max, r_max, s_min, v_max in param_grid_mod:
        mask = (
            (df['mom_5d'] <= m_max) &
            (df['rsi'] >= 30) & (df['rsi'] <= r_max) &
            (df['shadow_ratio'] >= s_min) &
            (df['vol_ratio'] <= v_max)
        )
        hits = df[mask & df['is_rally']]
        fails = df[mask & ~df['is_rally']]
        
        h = len(hits)
        f = len(fails)
        t = h+f
        
        if t >= 2:
             prec = h/t*100
             if prec >= 50:
                 print(f"MOD: M<={m_max} R<30-{r_max} S>={s_min} V<={v_max} -> {h}/{t} ({prec:.1f}%)")


if __name__ == "__main__":
    main()
