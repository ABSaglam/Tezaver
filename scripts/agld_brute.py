
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
    symbol = 'AGLDUSDT'
    print(f"🔨 BRUTE FORCE ANALYSIS: {symbol}")
    
    # 1. Load Data
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'], train_only=True) # DG Only!
    
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
    
    # Shadows
    df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
    df['range'] = df['high'] - df['low']
    df['shadow_ratio'] = df['lower_shadow'] / df['range']
    
    # Define Target (DG Only)
    df['is_rally'] = False
    for idx in range(len(df)-1):
        next_date = df.loc[idx+1, 'datetime'].date()
        if next_date in rally_results:
            df.loc[idx, 'is_rally'] = True
            
    # Remove NaN
    df = df.dropna().reset_index(drop=True)
    
    total_rallies = df['is_rally'].sum()
    print(f"Total DG Rallies in Dataset: {total_rallies}")
    
    # SWEEP 1: SUPERNOVA / SWEET SPOT
    print("\n--- MOMENTUM SWEEP (Mom >= X) ---")
    param_grid_mom = list(itertools.product(
        [20, 30, 40],        # mom_min
        [50, 60, 70, 80],    # rsi_max (cap)
        [30, 40, 50, 100],   # ema_max (cap)
        [2.0, 3.0, 5.0, 0]   # vol_min
    ))

    for m_min, r_max, e_max, v_min in param_grid_mom:
         mask = (
             (df['mom_5d'] >= m_min) & 
             (df['rsi'] <= r_max) & 
             (df['ema_dist'] <= e_max) & 
             (df['vol_ratio'] >= v_min)
         )
         hits = df[mask & df['is_rally']]
         fails = df[mask & ~df['is_rally']]
         
         h = len(hits)
         f = len(fails)
         t = h+f
         
         if t >= 3:
             prec = h/t*100
             if prec >= 40:
                 print(f"MOM: M>={m_min} R<={r_max} E<={e_max} V>={v_min} -> {h}/{t} ({prec:.1f}%)")

    # SWEEP 2: RATIONAL DIP (Relaxed Shadow)
    print("\n--- RATIONAL DIP SWEEP (Mom <= X) ---")
    param_grid_dip = list(itertools.product(
        [-5, -10, -15, -20], # mom_max
        [30, 40, 50],        # rsi_max
        [0.0, 0.1, 0.2],     # shadow_min (Relaxed)
        [0.5, 0.8, 1.0, 2.0] # vol_max (Dry up)
    ))

    for m_max, r_max, s_min, v_max in param_grid_dip:
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
         
         if t >= 3: # Changed from 2 to 3 for robustness
             prec = h/t*100
             if prec >= 40:
                 print(f"DIP: M<={m_max} R<={r_max} S>={s_min} V<={v_max} -> {h}/{t} ({prec:.1f}%)")
                 
    # FORENSICS: MOMENTUM
    print("\n--- FORENSICS: MOMENTUM CANDIDATES (M20+) ---")
    hits = df[(df['mom_5d'] >= 20) & df['is_rally']]
    for _, r in hits.iterrows():
        print(f"HIT: {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | E:{r['ema_dist']:.1f} | V:{r['vol_ratio']:.1f}")
        
    print("\n--- FORENSICS: DIP CANDIDATES (M-15) ---")
    hits = df[(df['mom_5d'] <= -15) & df['is_rally']]
    for _, r in hits.iterrows():
        print(f"HIT: {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | S:{r['shadow_ratio']:.2f} | V:{r['vol_ratio']:.1f}")
                 
if __name__ == "__main__":
    main()
