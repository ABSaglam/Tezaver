
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
    symbol = 'ACEUSDT'
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

    # 3. Identify Hits vs Fails (Baseline: mom_3d >= 10)
    hits = []
    fails = []

    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        
        # BASELINE RULE
        if row['mom_3d'] >= 10:
            next_date = df.loc[idx+1, 'datetime'].date()
            if next_date in rally_results:
                hits.append(row)
            else:
                fails.append(row)
                
    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    print(f"Scanning for rule: mom_3d >= 10...")
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
            if prec >= 80: # Filter for interesting ones
                 print(f"  vol_ratio >= {v}: {total} rem -> {prec:.1f}%")

    # 6. Check RSI Upper Limit (finding overbought fails)
    print("\nChecking RSI Upper Limit...")
    for r in [80, 85, 90]:
        h_rem = len(hits_df[hits_df['rsi'] < r])
        f_rem = len(fails_df[fails_df['rsi'] < r])
        total = h_rem + f_rem
        if total > 0:
             prec = h_rem / total * 100
             if prec > 44.9: # Better than baseline
                 print(f"  rsi < {r}: {total} rem -> {prec:.1f}%")

    # 7. Check Aggressive Momentum
    print("\nChecking Aggressive Combos...")
    for m3 in [15, 20, 25, 30, 35]:
        h_rem = len(hits_df[hits_df['mom_3d'] >= m3])
        f_rem = len(fails_df[fails_df['mom_3d'] >= m3])
        
        total = h_rem + f_rem
        if total > 0:
            prec = h_rem / total * 100
            if prec >= 80:
                print(f"  mom_3d >= {m3}: {total} rem -> {prec:.1f}%")
    
    # 8. Vol + Mom Combo (Aggressive)
    print("\nChecking Aggressive Vol + Mom Combos...")
    for v in [2.0, 3.0, 4.0]:
        for m3 in [15, 20, 25, 30, 35]:
            h_rem = len(hits_df[(hits_df['vol_ratio'] >= v) & (hits_df['mom_3d'] >= m3)])
            f_rem = len(fails_df[(fails_df['vol_ratio'] >= v) & (fails_df['mom_3d'] >= m3)])
            total = h_rem + f_rem
            if total > 2:
                 prec = h_rem / total * 100
                 if prec >= 90:
                     print(f"  vol>={v} & mom_3d>={m3}: {total} rem -> {prec:.1f}%")

    # 9. Super Mom5
    print("\nChecking Super Mom5...")
    for m5 in [15, 20, 25, 30, 35]:
        h_rem = len(hits_df[hits_df['mom_5d'] >= m5])
        f_rem = len(fails_df[fails_df['mom_5d'] >= m5])
        total = h_rem + f_rem
        if total > 0:
            prec = h_rem / total * 100
            if prec >= 60:
                print(f"  mom_5d >= {m5}: {total} rem -> {prec:.1f}%")

    # 10. Check EMA Distance
    print("\nChecking EMA Distance...")
    for e in [-5, 0, 5, 10]:
        h_rem = len(hits_df[hits_df['ema_dist'] >= e])
        f_rem = len(fails_df[fails_df['ema_dist'] >= e])
        total = h_rem + f_rem
        if total > 0:
             prec = h_rem / total * 100
             if prec > 50:
                 print(f"  ema_dist >= {e}: {total} rem -> {prec:.1f}%")

    # 11. EMA + Mom 3d Combo
    print("\nChecking EMA + Mom 3d Combos...")
    for e in [-5, 0, 5, 8, 10, 12, 15]:
        for m3 in [10, 15, 20, 25, 30]:
            h_rem = len(hits_df[(hits_df['ema_dist'] >= e) & (hits_df['mom_3d'] >= m3)])
            f_rem = len(fails_df[(fails_df['ema_dist'] >= e) & (fails_df['mom_3d'] >= m3)])
            total = h_rem + f_rem
            if total > 0:
                 prec = h_rem / total * 100
                 if prec >= 70:
                     print(f"  ema>={e} & mom3>={m3}: {h_rem}/{total} -> {prec:.1f}%")

    # 13. Triple Combos (EMA + Mom + Vol)
    print("\nChecking Triple Combos (EMA + Mom + Vol)...")
    for e in [-2, 0, 2, 5]:
        for m3 in [15, 20, 25]:
            for v in [1.5, 2.0, 3.0]:
                h_rem = len(hits_df[(hits_df['ema_dist'] >= e) & (hits_df['mom_3d'] >= m3) & (hits_df['vol_ratio'] >= v)])
                f_rem = len(fails_df[(fails_df['ema_dist'] >= e) & (fails_df['mom_3d'] >= m3) & (fails_df['vol_ratio'] >= v)])
                total = h_rem + f_rem
                if total > 0:
                     prec = h_rem / total * 100
                     if prec >= 80:
                         print(f"  ema>={e} & mom3>={m3} & vol>={v}: {h_rem}/{total} -> {prec:.1f}%")

    # 14. Check Mom 7d + EMA
    print("\nChecking Mom 7d + EMA...")
    # 15. VISUAL INSPECTION
    print("\n" + "="*80)
    print("👀 VISUAL INSPECTION (Raw Data)")
    print("="*80)
    print(f"{'Date':<12} | {'Res':<4} | {'MOM3':<6} | {'MOM5':<6} | {'EMA_D':<6} | {'VOL':<5} | {'RSI':<5}")
    print("-" * 80)
    
    # Print ALL HITS
    for _, row in hits_df.iterrows():
        print(f"{row['datetime'].date()} | HIT  | {row['mom_3d']:>6.1f} | {row['mom_5d']:>6.1f} | {row['ema_dist']:>6.1f} | {row['vol_ratio']:>5.1f} | {row['rsi']:>5.1f}")
        
    print("-" * 80)
    
    print("-" * 80)

    # 17. TARGETED HYPOTHESIS: EXTREME MOMENTUM (EMA > 5 + Mom3 > 22 + Vol < 4)
    print("\nChecking TARGETED MOMENTUM Hypothesis...")
    h_rem = len(hits_df[(hits_df['ema_dist'] >= 5) & (hits_df['mom_3d'] >= 22) & (hits_df['vol_ratio'] <= 4)])
    f_rem = len(fails_df[(fails_df['ema_dist'] >= 5) & (fails_df['mom_3d'] >= 22) & (fails_df['vol_ratio'] <= 4)])
    total = h_rem + f_rem
    perc = 0
    if total > 0: perc = h_rem / total * 100
    print(f"  Rule: ema>=5 & mom3>=22 & vol<=4 -> {h_rem}/{total} ({perc:.1f}%)")
    
    # 18. TARGETED DIP: EMA <= -10 + Mom3 >= 15
    print("\nChecking TARGETED DIP Hypothesis...")
    h_rem = len(hits_df[(hits_df['ema_dist'] <= -10) & (hits_df['mom_3d'] >= 15)])
    f_rem = len(fails_df[(fails_df['ema_dist'] <= -10) & (fails_df['mom_3d'] >= 15)])
    total = h_rem + f_rem
    perc = 0
    if total > 0: perc = h_rem / total * 100
    print(f"  Rule: ema<=-10 & mom3>=15 -> {h_rem}/{total} ({perc:.1f}%)")

    # 19. TARGETED: EMA > 0 + Mom3 > 20 + Vol < 3
    print("\nChecking TARGETED QUIET MOMENTUM Hypothesis...")
    h_rem = len(hits_df[(hits_df['ema_dist'] >= 0) & (hits_df['mom_3d'] >= 20) & (hits_df['vol_ratio'] <= 3)])
    f_rem = len(fails_df[(fails_df['ema_dist'] >= 0) & (fails_df['mom_3d'] >= 20) & (fails_df['vol_ratio'] <= 3)])
    total = h_rem + f_rem
    perc = 0
    if total > 0: perc = h_rem / total * 100
    print(f"  Rule: ema>=0 & mom3>=20 & vol<=3 -> {h_rem}/{total} ({perc:.1f}%)")
    
    # 21. FINAL CANDIDATE: EMA >= 5 + Mom3 >= 22 + Vol <= 4 + RSI < 80
    print("\nChecking FINAL CANDIDATE Rule...")
    h_rem = len(hits_df[(hits_df['ema_dist'] >= 5) & (hits_df['mom_3d'] >= 22) & (hits_df['vol_ratio'] <= 4) & (hits_df['rsi'] < 80)])
    f_rem = len(fails_df[(fails_df['ema_dist'] >= 5) & (fails_df['mom_3d'] >= 22) & (fails_df['vol_ratio'] <= 4) & (fails_df['rsi'] < 80)])
    total = h_rem + f_rem
    perc = 0
    if total > 0: perc = h_rem / total * 100
    print(f"  Rule: ema>=5 & mom3>=22 & vol<=4 & rsi<80 -> {h_rem}/{total} ({perc:.1f}%)")

if __name__ == "__main__":
    main()
