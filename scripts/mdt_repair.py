"""
MDTUSDT Repair Analysis
=======================
Rule: mom_5d >= 35 AND vol_ratio >= 2
Result: 21 signals, 18 hits, 3 fails (85.7% precision)

Objective: Analyze the 3 failures vs 18 hits to find a filter.
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'MDTUSDT'
    print(f"🔧 {symbol} REPAIR ANALYSIS")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Calculate indicators used in rule
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    # Calculate extra indicators for filtering
    df['mom_3d'] = (df['close'] / df['close'].shift(3) - 1) * 100
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_dist'] = (df['close'] / df['ema9'] - 1) * 100
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Identify Hits and Fails
    hits = []
    fails = []
    
    print(f"{'DATE':<12} | {'RES':<4} | {'MOM5':<6} | {'VOL':<5} | {'MOM3':<6} | {'EMA%':<6} | {'RSI':<5} | {'D_CH':<6}")
    print("-" * 75)
    
    for idx in range(25, len(df)-1):
        row = df.loc[idx]
        
        # Original Rule
        if row['mom_5d'] >= 35 and row['vol_ratio'] >= 2:
            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            
            res_str = "✅" if is_hit else "❌"
            print(f"{row['datetime'].date()} | {res_str} | {row['mom_5d']:5.1f} | {row['vol_ratio']:4.1f} | {row['mom_3d']:5.1f} | {row['ema_dist']:5.1f} | {row['rsi']:4.1f} | {row['daily_ch']:5.1f}")
            
            if is_hit:
                hits.append(row)
            else:
                fails.append(row)
                
    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    print("\n" + "="*70)
    print("🔍 FAILURE ANALYSIS")
    print("="*70)
    
    # Compare means
    compare_cols = ['mom_5d', 'vol_ratio', 'mom_3d', 'mom_7d', 'daily_ch', 'ema_dist', 'rsi']
    print(f"{'Indicator':<10} | {'Hits Avg':<8} | {'Fails Avg':<8} | {'Diff':<8}")
    print("-" * 50)
    for col in compare_cols:
        h_mean = hits_df[col].mean()
        f_mean = fails_df[col].mean()
        print(f"{col:<10} | {h_mean:8.2f} | {f_mean:8.2f} | {h_mean-f_mean:8.2f}")
        
    print("\n💡 POTENTIAL FILTERS:")
    # Check simple thresholds that exclude all fails but keep most hits
    for col in compare_cols:
        # Filter: val < min_fail OR val > max_fail
        min_fail = fails_df[col].min()
        max_fail = fails_df[col].max()
        
        # Test > Max Fail
        retained = len(hits_df[hits_df[col] > max_fail])
        if retained > 0:
            print(f"  {col} > {max_fail:.2f} -> Removes ALL fails, keeps {retained}/{len(hits)} hits")
            
        # Test < Min Fail
        retained = len(hits_df[hits_df[col] < min_fail])
        if retained > 0:
            print(f"  {col} < {min_fail:.2f} -> Removes ALL fails, keeps {retained}/{len(hits)} hits")

if __name__ == "__main__":
    main()
