
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
    symbol = 'ALGOUSDT'
    print(f"🔨 BRUTE FORCE ANALYSIS: {symbol}")
    
    # 1. Load Data
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'], train_only=True) # Focus on Top Tiers
    
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
    
    # Define Target
    df['is_rally'] = False
    for idx in range(len(df)-1):
        next_date = df.loc[idx+1, 'datetime'].date()
        if next_date in rally_results:
            df.loc[idx, 'is_rally'] = True
            
    # Remove NaN
    df = df.dropna().reset_index(drop=True)
    
    total_rallies = df['is_rally'].sum()
    print(f"Total DG Rallies in Dataset: {total_rallies}")
    
    # SWEEP 1: WIDE DIP SEARCH
    print("\n--- WIDE DIP SWEEP ---")
    param_grid_dip = list(itertools.product(
        [-5, -10, -15],      # mom_max
        [30, 40, 50],        # rsi_max
        [0.0, 0.1, 0.2],     # shadow_min (Relaxed)
        [1.0, 2.0, 3.0]      # vol_max
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
         
         if t >= 2:
             prec = h/t*100
             if prec >= 40:
                 print(f"DIP: M<={m_max} R<={r_max} S>={s_min} V<={v_max} -> {h}/{t} ({prec:.1f}%)")

    # SWEEP 2: MOMENTUM & VOL
    print("\n--- MOMENTUM & VOL SWEEP ---")
    param_grid_mom = list(itertools.product(
        [5, 10, 15, 20],     # mom_min
        [50, 60, 70, 80],    # rsi_max
        [1.0, 2.0, 3.0, 5.0] # vol_max
    ))
    
    for m_min, r_max, v_max in param_grid_mom:
        mask = (
            (df['mom_5d'] >= m_min) &
            (df['rsi'] <= r_max) &
            (df['vol_ratio'] <= v_max)
        )
        hits = df[mask & df['is_rally']]
        fails = df[mask & ~df['is_rally']]
         
        h = len(hits)
        f = len(fails)
        t = h+f
         
        if t >= 3:
             prec = h/t*100
             if prec >= 40:
                 print(f"MOM: M>={m_min} R<={r_max} V<={v_max} -> {h}/{t} ({prec:.1f}%)")
                 
    # SWEEP 3: ROCKET RE-FUEL (Steady Mom)
    print("\n--- ROCKET RE-FUEL SWEEP (Mom 10-25) ---")
    param_grid_refuel = list(itertools.product(
        [10, 11, 12, 13],    # mom_min
        [20, 25, 30],        # mom_max (Cap the mom to avoid blow-off)
        [75, 80, 85],        # rsi_max
        [1.5, 2.0, 3.0]      # vol_max (Quiet accumulation)
    ))
    
    for m_min, m_max, r_max, v_max in param_grid_refuel:
        mask = (
            (df['mom_5d'] >= m_min) &
            (df['mom_5d'] <= m_max) &
            (df['rsi'] <= r_max) &
            (df['vol_ratio'] <= v_max)
        )
        hits = df[mask & df['is_rally']]
        fails = df[mask & ~df['is_rally']]
         
        h = len(hits)
        f = len(fails)
        t = h+f
         
        if t >= 3:
             prec = h/t*100
             if prec >= 50:
                 print(f"REFUEL: {m_min}<=M<={m_max} R<={r_max} V<={v_max} -> {h}/{t} ({prec:.1f}%)")

    # SWEEP 4: DEEP VALUE DIP (RSI < 30 + Strong Shadow)
    print("\n--- DEEP VALUE DIP SWEEP ---")
    param_grid_deep = list(itertools.product(
        [-10, -15],          # mom_max
        [25, 30],            # rsi_max
        [0.2, 0.25, 0.3],    # shadow_min
        [1.5, 2.0, 3.0]      # vol_max
    ))
    
    for m_max, r_max, s_min, v_max in param_grid_deep:
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
         
        if t >= 2:
             prec = h/t*100
             if prec >= 40:
                 print(f"DEEP: M<={m_max} R<={r_max} S>={s_min} V<={v_max} -> {h}/{t} ({prec:.1f}%)")
                 
    # FORENSICS RE-FUEL
    print("\n--- FORENSICS: RE-FUEL CANDIDATES ---")
    mask_ref = (df['mom_5d'] >= 10) & (df['mom_5d'] <= 25) & (df['vol_ratio'] <= 2.0)
    hits = df[mask_ref & df['is_rally']]
    print("HITS:")
    for _, r in hits.iterrows():
        print(f"  {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | V:{r['vol_ratio']:.1f} | E:{r['ema_dist']:.1f}")
        
    print("FAILS (Sample):")
    fails = df[mask_ref & ~df['is_rally']]
    for _, r in fails.head(10).iterrows():
        print(f"  {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | V:{r['vol_ratio']:.1f} | E:{r['ema_dist']:.1f}")

if __name__ == "__main__":
    main()
