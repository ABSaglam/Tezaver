
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
    symbol = 'ACHUSDT'
    print(f"🔧 {symbol} REPAIR ANALYSIS")
    print("="*70)

    # 1. Load Data
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)

    # 2. Calculate Indicators
    df['mom_3d'] = (df['close'] / df['close'].shift(3) - 1) * 100
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_dist'] = (df['close'] / df['ema_50'] - 1) * 100

    # 3. Identify Hits vs Fails (Baseline: mom_5d >= 15)
    hits = []
    fails = []

    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        
        # BASELINE RULE: mom_5d >= 15 (from verification failure)
        if row['mom_5d'] >= 15:
            next_date = df.loc[idx+1, 'datetime'].date()
            if next_date in rally_results:
                hits.append(row)
            else:
                fails.append(row)
                
    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    print(f"Scanning for rule: mom_5d >= 15...")
    print(f"Hits: {len(hits_df)} | Fails: {len(fails_df)}")
    
    if len(fails_df) == 0:
        print("✅ Already 100% Precise!")
        return

    # 4. Compare Averages
    print("\n" + "="*70)
    print(f"🔍 COMPARISON (Averages)")
    print("="*70)
    print(f"{'Indicator':<10} | {'Hits Avg':<8} | {'Fails Avg':<9} | {'Diff':<8}")
    print("-" * 50)
    
    indicators = ['mom_3d', 'mom_5d', 'mom_7d', 'vol_ratio', 'rsi', 'daily_ch', 'ema_dist']
    
    for ind in indicators:
        h_avg = hits_df[ind].mean()
        f_avg = fails_df[ind].mean()
        diff = abs(h_avg - f_avg)
        print(f"{ind:<10} | {h_avg:>8.2f} | {f_avg:>9.2f} | {diff:>8.2f}")

    print("\n💡 POTENTIAL FILTERS:")
    
    # 5. Check Volume Thresholds
    print("Checking Volume Thresholds...")
    for v in [1.5, 2.0, 3.0, 4.0, 5.0]:
        h_rem = len(hits_df[hits_df['vol_ratio'] >= v])
        f_rem = len(fails_df[fails_df['vol_ratio'] >= v])
        total = h_rem + f_rem
        if total > 0:
            prec = h_rem / total * 100
            if prec >= 50: # Filter for interesting ones
                 print(f"  vol_ratio >= {v}: {h_rem}/{total} -> {prec:.1f}%")

    # 6. Check RSI Upper Limit
    print("\nChecking RSI Upper Limit...")
    for r in [80, 85, 90]:
        h_rem = len(hits_df[hits_df['rsi'] < r])
        f_rem = len(fails_df[fails_df['rsi'] < r])
        total = h_rem + f_rem
        if total > 0:
             prec = h_rem / total * 100
             if prec > 40: 
                 print(f"  rsi < {r}: {h_rem}/{total} -> {prec:.1f}%")

    # 7. Check Aggressive Momentum (3d)
    print("\nChecking Aggressive Mom 3d...")
    for m3 in [15, 20, 25, 30, 35]:
        h_rem = len(hits_df[hits_df['mom_3d'] >= m3])
        f_rem = len(fails_df[fails_df['mom_3d'] >= m3])
        total = h_rem + f_rem
        if total > 0:
            prec = h_rem / total * 100
            if prec >= 60:
                print(f"  mom_3d >= {m3}: {h_rem}/{total} -> {prec:.1f}%")

    # 9. CHECK MOM_5D + EMA_DIST COMBOS (Strongest Diffs)
    print("\nChecking Mom 5d + EMA Dist Combos...")
    for m5 in [25, 30, 35, 40, 45]:
        for e in [10, 20, 30, 40]:
            h_rem = len(hits_df[(hits_df['mom_5d'] >= m5) & (hits_df['ema_dist'] >= e)])
            f_rem = len(fails_df[(fails_df['mom_5d'] >= m5) & (fails_df['ema_dist'] >= e)])
            total = h_rem + f_rem
            if total > 0:
                prec = h_rem / total * 100
                if prec >= 75:
                    print(f"  mom5>={m5} & ema>={e}: {h_rem}/{total} -> {prec:.1f}%")

    # 10. CHECK MOM_7D (Highest Diff)
    print("\nChecking Mom 7d...")
    for m7 in [30, 40, 50, 60]:
        h_rem = len(hits_df[hits_df['mom_7d'] >= m7])
        f_rem = len(fails_df[fails_df['mom_7d'] >= m7])
        total = h_rem + f_rem
        if total > 0:
            prec = h_rem / total * 100
            if prec >= 70:
                print(f"  mom_7d >= {m7}: {h_rem}/{total} -> {prec:.1f}%")

    # 12. DETAILED FAILURE ANALYSIS
    print("\n" + "="*80)
    print("🕵️ DETAILED FAILURE ANALYSIS (Rule: mom_5d >= 35 & ema_dist >= 30)")
    print("="*80)
    
    rule_hits = hits_df[(hits_df['mom_5d'] >= 35) & (hits_df['ema_dist'] >= 30)]
    rule_fails = fails_df[(fails_df['mom_5d'] >= 35) & (fails_df['ema_dist'] >= 30)]
    
    print(f"Stats: Hits {len(rule_hits)} | Fails {len(rule_fails)}")
    print("-" * 80)
    print("REMAINING FAILS:")
    for _, row in rule_fails.iterrows():
        print(f"{row['datetime'].date()} | FAIL | {row['mom_3d']:>6.1f} | {row['mom_5d']:>6.1f} | {row['ema_dist']:>6.1f} | {row['vol_ratio']:>5.1f} | {row['rsi']:>5.1f}")

    print("-" * 80)
    print("REMAINING HITS:")
    for _, row in rule_hits.iterrows():
        print(f"{row['datetime'].date()} | HIT  | {row['mom_3d']:>6.1f} | {row['mom_5d']:>6.1f} | {row['ema_dist']:>6.1f} | {row['vol_ratio']:>5.1f} | {row['rsi']:>5.1f}")

    # 13. TRIPLE COMBOS (MOM + EMA + VOL)
    print("\nChecking Triple Combos (Mom5 + EMA + Vol)...")
    # 14. COMPOSITE HYPOTHESIS
    print("\nChecking COMPOSITE Hypothesis...")
    # Global: ema_dist >= 30 AND rsi < 90
    # Branch 1: mom_5d >= 80 (Supernova)
    # Branch 2: mom_5d >= 39 AND vol_ratio <= 2.2 (Quiet Grinder)
    
    rule_hits = []
    rule_fails = []
    
    for df_source, target_list in [(hits_df, rule_hits), (fails_df, rule_fails)]:
        for _, row in df_source.iterrows():
            if row['ema_dist'] >= 30 and row['rsi'] < 90:
                if row['mom_5d'] >= 80:
                    target_list.append(row)
                elif row['mom_5d'] >= 39 and row['vol_ratio'] <= 2.2:
                    target_list.append(row)
                    
    h_len = len(rule_hits)
    f_len = len(rule_fails)
    total = h_len + f_len
    perc = 0
    if total > 0: perc = h_len / total * 100
    
    print(f"  Composite Rule: Hits {h_len} | Fails {f_len} -> {perc:.1f}%")
    if f_len > 0:
        print("  REMAINING FAILS:")
        for row in rule_fails:
             print(f"    {row['datetime'].date()} | M5:{row['mom_5d']:.1f} | E:{row['ema_dist']:.1f} | V:{row['vol_ratio']:.1f} | R:{row['rsi']:.1f}")

    # 15. VISUAL INSPECTION
    print("\n" + "="*80)
    print("👀 VISUAL INSPECTION (Raw Data)")
    print("="*80)
    print(f"{'Date':<12} | {'Res':<4} | {'MOM3':<6} | {'MOM5':<6} | {'EMA_D':<6} | {'VOL':<5} | {'RSI':<5}")
    print("-" * 80)
    
    # Print TOP HITS (Up to 20)
    for _, row in hits_df.head(20).iterrows():
        print(f"{row['datetime'].date()} | HIT  | {row['mom_3d']:>6.1f} | {row['mom_5d']:>6.1f} | {row['ema_dist']:>6.1f} | {row['vol_ratio']:>5.1f} | {row['rsi']:>5.1f}")
        
    print("-" * 80)
    
    # Print TOP FAILS (High Vol)
    fails_sorted = fails_df.sort_values('vol_ratio', ascending=False).head(20)
    for _, row in fails_sorted.iterrows():
        print(f"{row['datetime'].date()} | FAIL | {row['mom_3d']:>6.1f} | {row['mom_5d']:>6.1f} | {row['ema_dist']:>6.1f} | {row['vol_ratio']:>5.1f} | {row['rsi']:>5.1f}")

if __name__ == "__main__":
    main()
