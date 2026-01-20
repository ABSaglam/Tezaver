"""
BONKUSDT Repair Analysis
========================
Rule: mom_7d >= 3
Result: 260 signals, 122 hits, 138 fails (46.9% precision)

Objective: Analyze the 138 failures vs 122 hits.
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
    print(f"🔧 {symbol} REPAIR ANALYSIS")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Indicators
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['mom_3d'] = (df['close'] / df['close'].shift(3) - 1) * 100
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    hits = []
    fails = []
    
    for idx in range(25, len(df)-1):
        row = df.loc[idx]
        
        # Rule
        if row['mom_7d'] >= 3:
            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            
            if is_hit:
                hits.append(row)
            else:
                fails.append(row)
                
    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    print(f"Hits: {len(hits_df)} | Fails: {len(fails_df)}")
    
    if not hits_df.empty and not fails_df.empty:
        print("\n" + "="*70)
        print("🔍 COMPARISON (Averages)")
        print("="*70)
        cols = ['mom_7d', 'mom_5d', 'mom_3d', 'vol_ratio', 'rsi', 'daily_ch']
        print(f"{'Indicator':<10} | {'Hits Avg':<8} | {'Fails Avg':<8} | {'Diff':<8}")
        print("-" * 50)
        for col in cols:
            h_mean = hits_df[col].mean()
            f_mean = fails_df[col].mean()
            print(f"{col:<10} | {h_mean:8.2f} | {f_mean:8.2f} | {h_mean-f_mean:8.2f}")

        print("\n💡 POTENTIAL FILTERS:")
        # Strategy: Iterate potential thresholds and check precision
        best_prec = 0
        best_rule = ""
        
        # Grid Search for simple filters
        # e.g. vol_ratio >= X, rsi <= Y
        
        print("Checking Volume Thresholds...")
        for v in [1.0, 1.5, 2.0, 2.5, 3.0]:
            # Apply filter to the base set (which is already mom_7d >= 3)
            # Hits remaining
            h_rem = len(hits_df[hits_df['vol_ratio'] >= v])
            # Fails remaining
            f_rem = len(fails_df[fails_df['vol_ratio'] >= v])
            
            total = h_rem + f_rem
            if total > 5:
                prec = h_rem / total * 100
                if prec >= 60:
                    print(f"  vol_ratio >= {v}: {total} remaining, {h_rem} hits -> {prec:.1f}%")
                    
        print("\nChecking RSI Thresholds (Upper Limit)...")
        for r in [80, 75, 70, 65, 60]:
            # Apply filter
            h_rem = len(hits_df[hits_df['rsi'] <= r])
            f_rem = len(fails_df[fails_df['rsi'] <= r])
            
            total = h_rem + f_rem
            if total > 5:
                prec = h_rem / total * 100
                if prec >= 60:
                    print(f"  rsi <= {r}: {total} remaining, {h_rem} hits -> {prec:.1f}%")

        print("\nChecking RSI Thresholds (Lower Limit)...")
        for r in [30, 40, 50, 60]:
            # Apply filter
            h_rem = len(hits_df[hits_df['rsi'] >= r])
            f_rem = len(fails_df[fails_df['rsi'] >= r])
            
            total = h_rem + f_rem
            if total > 5:
                prec = h_rem / total * 100
                if prec >= 60:
                    print(f"  rsi >= {r}: {total} remaining, {h_rem} hits -> {prec:.1f}%")
                    
        print("\nChecking Aggressive Combos...")
        # 1. High Volume + High Momentum
        for v in [2.5, 3.0, 3.5, 4.0]:
            for m7 in [10, 15, 20, 25]:
                h_rem = len(hits_df[(hits_df['vol_ratio'] >= v) & (hits_df['mom_7d'] >= m7)])
                f_rem = len(fails_df[(fails_df['vol_ratio'] >= v) & (fails_df['mom_7d'] >= m7)])
                total = h_rem + f_rem
                if total > 3:
                     prec = h_rem / total * 100
                     if prec >= 90:
                         print(f"  vol>={v} & mom_7d>={m7}: {total} rem -> {prec:.1f}%")

        # 2. High Volume + RSI Range
        print("\nChecking Vol + RSI Combos...")
        for v in [2.5, 3.0, 3.5]:
            for r_max in [75, 80, 85]:
                h_rem = len(hits_df[(hits_df['vol_ratio'] >= v) & (hits_df['rsi'] <= r_max)])
                f_rem = len(fails_df[(fails_df['vol_ratio'] >= v) & (fails_df['rsi'] <= r_max)])
                total = h_rem + f_rem
                if total > 3:
                     prec = h_rem / total * 100
                     if prec >= 90:
                         print(f"  vol>={v} & rsi<={r_max}: {total} rem -> {prec:.1f}%")

        # 3. Super Volume
        print("\nChecking Super Volume...")
        for v in [4.0, 5.0, 6.0, 7.0]:
            h_rem = len(hits_df[hits_df['vol_ratio'] >= v])
            f_rem = len(fails_df[fails_df['vol_ratio'] >= v])
            total = h_rem + f_rem
            if total > 2:
                prec = h_rem / total * 100
                print(f"  vol>={v}: {total} rem -> {prec:.1f}%")

if __name__ == "__main__":
    main()
