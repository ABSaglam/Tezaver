
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
    symbol = 'ACMUSDT'
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

    # 3. Identify Hits vs Fails (Baseline: mom_5d >= 10)
    hits = []
    fails = []

    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        
        # BASELINE RULE: mom_5d >= 10 (Generic Momentum)
        if row['mom_5d'] >= 10:
            next_date = df.loc[idx+1, 'datetime'].date()
            if next_date in rally_results:
                hits.append(row)
            else:
                fails.append(row)
                
    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    print(f"Scanning for rule: mom_5d >= 10 (Baseline)...")
    print(f"Hits: {len(hits_df)} | Fails: {len(fails_df)}")
    
    # 4. Compare Averages
    print("\n" + "="*70)
    print(f"🔍 COMPARISON (Averages)")
    print("="*70)
    print(f"{'Indicator':<10} | {'Hits Avg':<8} | {'Fails Avg':<9} | {'Diff':<8}")
    print("-" * 50)
    
    indicators = ['mom_3d', 'mom_5d', 'mom_7d', 'vol_ratio', 'rsi', 'daily_ch', 'ema_dist']
    
    for ind in indicators:
        h_avg = hits_df[ind].mean() if not hits_df.empty else 0
        f_avg = fails_df[ind].mean() if not fails_df.empty else 0
        diff = abs(h_avg - f_avg)
        print(f"{ind:<10} | {h_avg:>8.2f} | {f_avg:>9.2f} | {diff:>8.2f}")

    print("\n💡 POTENTIAL FILTERS:")
    
    # 5. Check Volume Thresholds
    print("Checking Volume Thresholds...")
    for v in [1.5, 2.0, 3.0, 4.0]:
        h_rem = len(hits_df[hits_df['vol_ratio'] >= v])
        f_rem = len(fails_df[fails_df['vol_ratio'] >= v])
        total = h_rem + f_rem
        if total > 0:
            prec = h_rem / total * 100
            if prec >= 40:
                 print(f"  vol_ratio >= {v}: {h_rem}/{total} -> {prec:.1f}%")

    # 6. Check Aggressive Mom 5d
    print("\nChecking Aggressive Mom 5d...")
    for m5 in [15, 20, 25, 30, 35]:
        h_rem = len(hits_df[hits_df['mom_5d'] >= m5])
        f_rem = len(fails_df[fails_df['mom_5d'] >= m5])
        total = h_rem + f_rem
        if total > 0:
            prec = h_rem / total * 100
            if prec >= 50:
                print(f"  mom_5d >= {m5}: {h_rem}/{total} -> {prec:.1f}%")

    # 7. Check EMA Dist
    print("\nChecking EMA Dist...")
    for e in [10, 20, 30, 40]:
        h_rem = len(hits_df[hits_df['ema_dist'] >= e])
        f_rem = len(fails_df[fails_df['ema_dist'] >= e])
        total = h_rem + f_rem
        if total > 0:
            prec = h_rem / total * 100
            if prec >= 50:
                print(f"  ema_dist >= {e}: {h_rem}/{total} -> {prec:.1f}%")
                
    # 9. REFINING HIGH VOLUME (Vol >= 3.5)
    print("\n" + "="*80)
    print("🔍 REFINING CANDIDATE H1 (Vol >= 4.0)")
    print("="*80)
    
    # Base H1 Rule
    rule_hits = []
    rule_fails = []
    
    for df_source, target_list in [(hits_df, rule_hits), (fails_df, rule_fails)]:
        for _, row in df_source.iterrows():
            if row['vol_ratio'] >= 4.0:
                target_list.append(row)
                
    h_len = len(rule_hits)
    f_len = len(rule_fails)
    total = h_len + f_len
    if total > 0:
        print(f"Base H1 (Vol >= 4.0): {h_len}/{total} -> {h_len/total*100:.1f}%")
        
    print("\n  Failures in Base H1:")
    for row in rule_fails:
        print(f"    {row['datetime'].date()} | M5:{row['mom_5d']:.1f} | E:{row['ema_dist']:.1f} | V:{row['vol_ratio']:.1f} | R:{row['rsi']:.1f} | DCH:{row['daily_ch']:.1f}")

    # 10. FILTER SWEEPS ON H1
    print("\n  Testing Filters on H1...")
    
    # Mom5 Floor
    for m in [15, 20, 25]:
        h_cnt = sum(1 for row in rule_hits if row['mom_5d'] >= m)
        f_cnt = sum(1 for row in rule_fails if row['mom_5d'] >= m)
        tot = h_cnt + f_cnt
        if tot > 0: print(f"    + mom_5d >= {m}: {h_cnt}/{tot} -> {h_cnt/tot*100:.1f}%")

    # EMA Dist Floor/Cap
    for e in [0, 5, 10]:
        h_cnt = sum(1 for row in rule_hits if row['ema_dist'] >= e)
        f_cnt = sum(1 for row in rule_fails if row['ema_dist'] >= e)
        tot = h_cnt + f_cnt
        if tot > 0: print(f"    + ema_dist >= {e}: {h_cnt}/{tot} -> {h_cnt/tot*100:.1f}%")
        
    # RSI
    for r in [60, 65, 70]:
        h_cnt = sum(1 for row in rule_hits if row['rsi'] >= r)
        f_cnt = sum(1 for row in rule_fails if row['rsi'] >= r)
        tot = h_cnt + f_cnt
        if tot > 0: print(f"    + rsi >= {r}: {h_cnt}/{tot} -> {h_cnt/tot*100:.1f}%")

    # 12. COMPOSITE STRATEGY ANALYSIS
    print("\n" + "="*80)
    print("🔍 COMPOSITE ANALYSIS")
    print("="*80)
    
    # GROUP A: SUPERNOVA (Vol >= 4.0)
    print("Group A: Vol >= 4.0")
    g_a_hits = [r for idx, r in hits_df.iterrows() if r['vol_ratio'] >= 4.0]
    g_a_fails = [r for idx, r in fails_df.iterrows() if r['vol_ratio'] >= 4.0]
    
    print(f"  Total: {len(g_a_hits)} Hits, {len(g_a_fails)} Fails")
    print("  Hits (Daily Ch): " + ", ".join([f"{r['daily_ch']:.1f}" for r in g_a_hits]))
    print("  Fails (Daily Ch): " + ", ".join([f"{r['daily_ch']:.1f}" for r in g_a_fails]))
    
    a_kept = sum(1 for r in g_a_hits if r['daily_ch'] >= 10)
    a_fail_kept = sum(1 for r in g_a_fails if r['daily_ch'] >= 10)
    print(f"  Filter (DailyCh >= 10): {a_kept} Hits, {a_fail_kept} Fails")
    
    # GROUP B: MEDIUM VOLUME (Vol 2.5 - 4.0)
    print("\nGroup B: Vol 2.5 - 4.0")
    g_b_hits = [r for idx, r in hits_df.iterrows() if r['vol_ratio'] >= 2.5 and r['vol_ratio'] < 4.0]
    g_b_fails = [r for idx, r in fails_df.iterrows() if r['vol_ratio'] >= 2.5 and r['vol_ratio'] < 4.0]
    
    print(f"  Total: {len(g_b_hits)} Hits, {len(g_b_fails)} Fails")
    
    # Inspect Group B Fails
    print("  Top Fails in Group B:")
    for r in g_b_fails[:10]:
         print(f"    {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | E:{r['ema_dist']:.1f} | V:{r['vol_ratio']:.1f} | R:{r['rsi']:.1f} | DCH:{r['daily_ch']:.1f}")

    # Sweep Filters on Group B
    print("  Filters on Group B:")
    for m in [15, 20]:
        for r in [60, 65, 70]:
             k_h = sum(1 for row in g_b_hits if row['mom_5d'] >= m and row['rsi'] >= r)
             k_f = sum(1 for row in g_b_fails if row['mom_5d'] >= m and row['rsi'] >= r)
             tot = k_h + k_f
             if tot > 0: print(f"    M>={m} & R>={r}: {k_h}/{tot} -> {k_h/tot*100:.1f}%")

    # 15. VISUAL INSPECTION
    print("\n" + "="*80)
    print("👀 VISUAL INSPECTION (Raw Data)")
    print("="*80)
    print(f"{'Date':<12} | {'Res':<4} | {'MOM3':<6} | {'MOM5':<6} | {'EMA_D':<6} | {'DOL_CH':<6} | {'VOL':<5} | {'RSI':<5}")
    print("-" * 80)
    
    # Print TOP HITS
    if not hits_df.empty:
        for _, row in hits_df.head(15).iterrows():
            print(f"{row['datetime'].date()} | HIT  | {row['mom_3d']:>6.1f} | {row['mom_5d']:>6.1f} | {row['ema_dist']:>6.1f} | {row['daily_ch']:>6.1f} | {row['vol_ratio']:>5.1f} | {row['rsi']:>5.1f}")
        
    print("-" * 80)
    
    # Print TOP FAILS
    if not fails_df.empty:
        fails_sorted = fails_df.sort_values('mom_5d', ascending=False).head(15)
        for _, row in fails_sorted.iterrows():
            print(f"{row['datetime'].date()} | FAIL | {row['mom_3d']:>6.1f} | {row['mom_5d']:>6.1f} | {row['ema_dist']:>6.1f} | {row['daily_ch']:>6.1f} | {row['vol_ratio']:>5.1f} | {row['rsi']:>5.1f}")

if __name__ == "__main__":
    main()
