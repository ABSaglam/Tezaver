
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
    symbol = 'ADAUSDT'
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
    # Using generic baseline. ADA is a major coin!
    hits = []
    fails = []

    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        
        # BASELINE RULE: mom_5d >= 10
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
    
    # 5. Check Low Vol (Blue Chip Hypothesis)
    print("Checking Volume Thresholds...")
    for v in [1.5, 2.0, 3.0, 4.0]:
        h_rem = len(hits_df[hits_df['vol_ratio'] >= v])
        f_rem = len(fails_df[fails_df['vol_ratio'] >= v])
        total = h_rem + f_rem
        if total > 0:
            prec = h_rem / total * 100
            print(f"  vol_ratio >= {v}: {h_rem}/{total} -> {prec:.1f}%")

    # 6. Check High Momentum (Aggressive)
    print("\nChecking Aggressive Mom 5d...")
    for m5 in [15, 20, 25]:
        h_rem = len(hits_df[hits_df['mom_5d'] >= m5])
        f_rem = len(fails_df[fails_df['mom_5d'] >= m5])
        total = h_rem + f_rem
        if total > 0:
            print(f"  mom_5d >= {m5}: {h_rem}/{total} -> {prec:.1f}%")

    # 7. Check EMA Dist
    print("\nChecking EMA Dist...")
    for e in [10, 20, 30]:
        h_rem = len(hits_df[hits_df['ema_dist'] >= e])
        f_rem = len(fails_df[fails_df['ema_dist'] >= e])
        total = h_rem + f_rem
        if total > 0:
            print(f"  ema_dist >= {e}: {h_rem}/{total} -> {prec:.1f}%")
            
    # 12. REFINING H1 (Mom5 >= 25 + EMA >= 20)
    print("\n" + "="*80)
    print("🔍 REFINING SELECTED H1 (Mom5 >= 25 + EMA >= 20)")
    print("="*80)
    
    # Base H1 Rule
    rule_hits = []
    rule_fails = []
    
    for df_source, target_list in [(hits_df, rule_hits), (fails_df, rule_fails)]:
        for _, row in df_source.iterrows():
            if (row['mom_5d'] >= 25 and row['ema_dist'] >= 20):
                target_list.append(row)
                
    h_len = len(rule_hits)
    f_len = len(rule_fails)
    total = h_len + f_len
    if total > 0:
        print(f"Base H1: {h_len}/{total} -> {h_len/total*100:.1f}%")
        
    print("\n  Failures in Base H1:")
    for row in rule_fails:
        print(f"    {row['datetime'].date()} | M5:{row['mom_5d']:.1f} | E:{row['ema_dist']:.1f} | V:{row['vol_ratio']:.1f} | R:{row['rsi']:.1f}")

    # 14. REFINING RATIONAL MOMENTUM (H1 + RSI <= 85)
    print("\n" + "="*80)
    print("🔍 REFINING RATIONAL MOMENTUM (H1 + RSI <= 85)")
    print("="*80)
    
    # H1 + RSI <= 85
    h2_hits = []
    h2_fails = []
    
    for df_source, target_list in [(hits_df, h2_hits), (fails_df, h2_fails)]:
        for _, row in df_source.iterrows():
            if (row['mom_5d'] >= 25 and row['ema_dist'] >= 20 and
                row['rsi'] <= 85):
                target_list.append(row)
                
    h_len = len(h2_hits)
    f_len = len(h2_fails)
    total = h_len + f_len
    if total > 0:
        print(f"H1 + RSI <= 85: {h_len}/{total} -> {h_len/total*100:.1f}%")
        
    print("\n  Failures in Rational Momentum:")
    for row in h2_fails:
        print(f"    {row['datetime'].date()} | M5:{row['mom_5d']:.1f} | M7:{row['mom_7d']:.1f} | E:{row['ema_dist']:.1f} | V:{row['vol_ratio']:.1f} | R:{row['rsi']:.1f}")

    print("\n  Testing Filters on Rational Momentum...")
    # Mom7
    for m in [20, 25, 30]:
        h_cnt = sum(1 for row in h2_hits if row['mom_7d'] >= m)
        f_cnt = sum(1 for row in h2_fails if row['mom_7d'] >= m)
        tot = h_cnt + f_cnt
        if tot > 0: print(f"    + mom_7d >= {m}: {h_cnt}/{tot} -> {h_cnt/tot*100:.1f}%")
        
    # EMA
    for e in [25, 30, 35]:
        h_cnt = sum(1 for row in h2_hits if row['ema_dist'] >= e)
        f_cnt = sum(1 for row in h2_fails if row['ema_dist'] >= e)
        tot = h_cnt + f_cnt
        if tot > 0: print(f"    + ema_dist >= {e}: {h_cnt}/{tot} -> {h_cnt/tot*100:.1f}%")

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
