"""
ACAUSDT Repair Analysis
=======================
Rule: mom_3d >= 15
Result: 35 signals, 23 hits, 12 fails (65.7% precision)

Objective: Analyze the 12 failures vs 23 hits.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ACAUSDT'
    print(f"🔧 {symbol} REPAIR ANALYSIS")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Indicators
    df['mom_3d'] = (df['close'] / df['close'].shift(3) - 1) * 100
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    # EMA distance
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_dist'] = (df['close'] / df['ema9'] - 1) * 100
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    hits = []
    fails = []
    
    print(f"Scanning for rule: mom_3d >= 15...")
    
    for idx in range(25, len(df)-1):
        row = df.loc[idx]
        
        # Rule
        if row['mom_3d'] >= 15:
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
        cols = ['mom_3d', 'mom_5d', 'mom_7d', 'vol_ratio', 'rsi', 'daily_ch', 'ema_dist']
        print(f"{'Indicator':<10} | {'Hits Avg':<8} | {'Fails Avg':<8} | {'Diff':<8}")
        print("-" * 50)
        for col in cols:
            h_mean = hits_df[col].mean()
            f_mean = fails_df[col].mean()
            print(f"{col:<10} | {h_mean:8.2f} | {f_mean:8.2f} | {h_mean-f_mean:8.2f}")

        print("\n💡 POTENTIAL FILTERS:")
        
        # 1. Volume Thresholds
        print("Checking Volume Thresholds...")
        for v in [1.5, 2.0, 2.5, 3.0]:
            h_rem = len(hits_df[hits_df['vol_ratio'] >= v])
            f_rem = len(fails_df[fails_df['vol_ratio'] >= v])
            total = h_rem + f_rem
            if total > 3:
                prec = h_rem / total * 100
                if prec >= 80:
                    print(f"  vol_ratio >= {v}: {total} remaining, {h_rem} hits -> {prec:.1f}%")

        # 2. RSI Thresholds (Upper Limit)
        print("\nChecking RSI Upper Limit...")
        for r in [85, 80, 75, 70]:
            h_rem = len(hits_df[hits_df['rsi'] <= r])
            f_rem = len(fails_df[fails_df['rsi'] <= r])
            total = h_rem + f_rem
            if total > 3:
                prec = h_rem / total * 100
                if prec >= 80:
                    print(f"  rsi <= {r}: {total} remaining, {h_rem} hits -> {prec:.1f}%")
                    
        # 3. Aggressive Combos
        print("\nChecking Aggressive Combos...")
        for m3 in [20, 25, 30]:
            h_rem = len(hits_df[hits_df['mom_3d'] >= m3])
            f_rem = len(fails_df[fails_df['mom_3d'] >= m3])
            total = h_rem + f_rem
            if total > 2:
                prec = h_rem / total * 100
                if prec >= 80:
                    print(f"  mom_3d >= {m3}: {total} rem -> {prec:.1f}%")
        
        # 4. Vol + Mom Combo (Aggressive)
        print("\nChecking Aggressive Vol + Mom Combos...")
        for v in [2.0, 2.5, 3.0, 4.0, 5.0]:
            for m3 in [20, 25, 30, 35, 40]:
                h_rem = len(hits_df[(hits_df['vol_ratio'] >= v) & (hits_df['mom_3d'] >= m3)])
                f_rem = len(fails_df[(fails_df['vol_ratio'] >= v) & (fails_df['mom_3d'] >= m3)])
                total = h_rem + f_rem
                if total > 2:
                     prec = h_rem / total * 100
                     if prec >= 90:
                         print(f"  vol>={v} & mom_3d>={m3}: {total} rem -> {prec:.1f}%")

        # 5. Very High Mom3 Only
        print("\nChecking Super Mom3...")
        for m3 in [35, 40, 45, 50, 60]:
            h_rem = len(hits_df[hits_df['mom_3d'] >= m3])
            f_rem = len(fails_df[fails_df['mom_3d'] >= m3])
            total = h_rem + f_rem
            if total > 2:
                prec = h_rem / total * 100
                print(f"  mom_3d >= {m3}: {total} rem -> {prec:.1f}%")

        # 6. Mom7 Check (since diff was high)
        print("\nChecking Mom 7d...")
        for m7 in [20, 30, 40, 50]:
             h_rem = len(hits_df[hits_df['mom_7d'] >= m7])
             f_rem = len(fails_df[fails_df['mom_7d'] >= m7])
             total = h_rem + f_rem
             if total > 2:
                 prec = h_rem / total * 100
                 if prec >= 90:
                     print(f"  mom_7d >= {m7}: {total} rem -> {prec:.1f}%")

if __name__ == "__main__":
    main()
