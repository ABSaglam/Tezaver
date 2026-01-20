
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
    symbol = 'AERGOUSDT'
    print(f"🔨 BRUTE FORCE ANALYSIS: {symbol}")
    
    # 1. Load Data
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)

    # 2. Indicators
    df['mom_3d'] = (df['close'] / df['close'].shift(3) - 1) * 100
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    
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
    
    # 3. Param Grid
    params = {
        'mom_5d_min': [-20, -10, 0, 10, 20],
        'mom_5d_max': [-5, 0, 5, 20, 100],
        'rsi_min': [0, 30, 40, 50],
        'rsi_max': [40, 50, 60, 80, 100],
        'ema_dist_max': [-10, 0, 10, 30, 100],
        'vol_ratio_max': [1.0, 2.0, 5.0, 100.0]
    }
    
    best_prec = 0
    best_rule = ""
    
    # Random sampling or structured sweep?
    # Let's do structured sweep of 3-component rules
    
    print("Sweeping...")
    
    count = 0
    
    # mom_5d range + rsi range using itertools
    for m_min in [-30, -20, -10, 0, 10]:
        for e_max in [0, 10, 30, 40, 100]:
            for r_max in [40, 50, 60, 80, 100]:
                for v_max in [1.0, 2.0, 100.0]:
                        
                    # Rule: mom >= m_min AND ema <= e_max AND rsi <= r_max AND vol <= v_max
                    # Wait, mom >= m_min is standard. But we have dips (mom <= X).
                    # Let's try flexible Momentum: Mom <= X OR Mom >= Y?
                    # For brute force, let's stick to "Mom >= X" (standard) and "Mom <= X" (Dip) separate sweeps.
                    pass

    # SWEEP 1: DIP FOCUS (Mom5 <= X)
    print("\n--- DIP SWEEP (Mom <= X) ---")
    param_grid = list(itertools.product(
        [-5, -10, -15, -20], # mom_max
        [30, 40, 50, 60],    # rsi_max
        [-5, 0, 10],         # ema_max
        [0.5, 1.0, 2.0, 100],# vol_max
        [0, -3, -5, 100]     # dch_max
    ))
    
    for m_max, r_max, e_max, v_max, d_max in param_grid:
         # Rule: Mom5 <= m_max & RSI <= r_max & EMA <= e_max & Vol <= v_max & DCh <= d_max
         mask = (
             (df['mom_5d'] <= m_max) & 
             (df['rsi'] <= r_max) & 
             (df['ema_dist'] <= e_max) &
             (df['vol_ratio'] <= v_max) &
             (df['daily_ch'] <= d_max)
         )
         hits = df[mask & df['is_rally']]
         fails = df[mask & ~df['is_rally']]
         
         h = len(hits)
         f = len(fails)
         t = h+f
         
         if t >= 3:
             prec = h/t*100
             if prec >= 50: # Lower threshold to see partials
                 print(f"DIP: M<={m_max} R<={r_max} E<={e_max} V<={v_max} D<={d_max} -> {h}/{t} ({prec:.1f}%)")

    # SWEEP 2: MOMENTUM FOCUS (Mom5 >= X)
    print("\n--- MOMENTUM SWEEP (Mom >= X) ---")
    param_grid_mom = list(itertools.product(
        [5, 10, 15, 20],     # mom_min
        [60, 70, 80, 100],   # rsi_max (cap)
        [20, 30, 40, 100],   # ema_max (cap)
        [2.0, 3.0, 100]      # vol_max
    ))
    
    for m_min, r_max, e_max, v_max in param_grid_mom:
         # Rule: Mom5 >= m_min & RSI <= r_max & EMA <= e_max & Vol <= v_max
         mask = (
             (df['mom_5d'] >= m_min) & 
             (df['rsi'] <= r_max) & 
             (df['ema_dist'] <= e_max) &
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
                 print(f"MOM: M>={m_min} R<={r_max} E<={e_max} V<={v_max} -> {h}/{t} ({prec:.1f}%)")

    # DOUGHNUT HOLE TEST
    print("\n--- DOUGHNUT HOLE TEST (Dip) ---")
    # Rule: Mom5 <= -15 AND (RSI >= 40 OR RSI <= 25)
    # Plus standard caps: E <= 10, V <= 2.0, D <= -5
    
    mask_dip = (df['mom_5d'] <= -15) & (df['ema_dist'] <= 10) & (df['vol_ratio'] <= 2.0) & (df['daily_ch'] <= -5)
    mask_hole = (df['rsi'] >= 40) | (df['rsi'] <= 25)
    
    final_mask = mask_dip & mask_hole
    
    hits = df[final_mask & df['is_rally']]
    fails = df[final_mask & ~df['is_rally']]
    
    h = len(hits)
    f = len(fails)
    t = h+f
    print(f"Doughnut Hole Rule: {h}/{t}")
    if t > 0:
        print(f"Precision: {h/t*100:.1f}%")
        print("HITS:")
        for _, r in hits.iterrows():
            print(f"  {r['datetime'].date()} | R:{r['rsi']:.1f}")
        print("FAILS:")
        for _, r in fails.iterrows():
            print(f"  {r['datetime'].date()} | R:{r['rsi']:.1f}")

    # FORENSICS ON BEST DIP CANDIDATE
    print("\n--- FORENSICS: M<=-15 R<=60 E<=10 V<=2.0 D<=-5 ---")
    m_max = -15
    r_max = 60
    e_max = 10
    v_max = 2.0
    d_max = -5
    
    mask = (
         (df['mom_5d'] <= m_max) & 
         (df['rsi'] <= r_max) & 
         (df['ema_dist'] <= e_max) &
         (df['vol_ratio'] <= v_max) &
         (df['daily_ch'] <= d_max)
    )
    hits = df[mask & df['is_rally']]
    fails = df[mask & ~df['is_rally']]
    
    print("HITS:")
    for _, r in hits.iterrows():
        print(f"  {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | E:{r['ema_dist']:.1f} | V:{r['vol_ratio']:.1f} | D:{r['daily_ch']:.1f}")
        
    print("FAILS:")
    for _, r in fails.iterrows():
        print(f"  {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | E:{r['ema_dist']:.1f} | V:{r['vol_ratio']:.1f} | D:{r['daily_ch']:.1f}")
                         
    # SWEEP 3: UNUSUAL (RSI High but Mom Low?)
    # "Divergence Scans"
    # RSI > 50 but Mom5 < 0?
    print("\n--- DIVERGENCE SWEEP (Mom < 0 but RSI > 40) ---")
    mask_base = (df['mom_5d'] < 0) & (df['rsi'] > 40)
    hits = df[mask_base & df['is_rally']]
    fails = df[mask_base & ~df['is_rally']]
    print(f"Base Divergence: {len(hits)}/{len(hits)+len(fails)}")

if __name__ == "__main__":
    main()
