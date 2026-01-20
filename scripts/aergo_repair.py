
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
    symbol = 'AERGOUSDT'
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

    # 3. BLIND SCAN (Find matches first)
    print("\n" + "="*80)
    print("👀 BLIND SCAN: INSPECTING ALL RALLY DAYS")
    print("="*80)
    
    # DEBUG: Check Date Ranges
    min_date = df['datetime'].min().date()
    max_date = df['datetime'].max().date()
    print(f"Data Range: {min_date} to {max_date}")
    
    rally_dates = sorted(list(rally_results.keys()))
    if rally_dates:
        print(f"Rally Range: {rally_dates[0]} to {rally_dates[-1]}")
        print(f"Total Rallies in DB: {len(rally_dates)}")
        
        # Check specific years
        r_2023 = [d for d in rally_dates if d.year == 2023]
        r_2024 = [d for d in rally_dates if d.year == 2024]
        print(f"Rallies in 2023: {len(r_2023)}")
        print(f"Rallies in 2024: {len(r_2024)}")
    else:
        print("❌ NO RALLIES IN DB HELP!")

    hits = []
    fails = []
    
    # Iterate to find ALL rallies
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        next_date = df.loc[idx+1, 'datetime'].date()
        
        if next_date in rally_results:
            tier = rally_results[next_date][0]
            print(f"{row['datetime'].date()} -> {next_date} ({tier}) | M5:{row['mom_5d']:.1f} | M3:{row['mom_3d']:.1f} | E:{row['ema_dist']:.1f} | DCH:{row['daily_ch']:.1f} | R:{row['rsi']:.1f}")
            hits.append(row)
        else:
            fails.append(row)

    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    if hits_df.empty:
        print("❌ NO RALLIES FOUND IN DATA PERIOD!")
        return

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

    # 9. DIP BUYING STRATEGIES
    print("\n" + "="*80)
    print("🔍 TESTING DIP BUYING STRATEGIES")
    print("="*80)
    
    # 1. Negative Mom5
    for m in [0, -5, -10, -15]:
        h_cnt = len(hits_df[hits_df['mom_5d'] <= m])
        f_cnt = len(fails_df[fails_df['mom_5d'] <= m])
        total = h_cnt + f_cnt
        if total > 0:
            print(f"mom_5d <= {m}: {h_cnt}/{total} -> {h_cnt/total*100:.1f}%")
            
    # 2. Negative Daily Ch
    for d in [0, -3, -5, -7]:
        h_cnt = len(hits_df[hits_df['daily_ch'] <= d])
        f_cnt = len(fails_df[fails_df['daily_ch'] <= d])
        total = h_cnt + f_cnt
        if total > 0:
            print(f"daily_ch <= {d}: {h_cnt}/{total} -> {h_cnt/total*100:.1f}%")

    # 3. Negative EMA Dist
    for e in [0, -5, -10, -15]:
        h_cnt = len(hits_df[hits_df['ema_dist'] <= e])
        f_cnt = len(fails_df[fails_df['ema_dist'] <= e])
        total = h_cnt + f_cnt
        if total > 0:
            print(f"ema_dist <= {e}: {h_cnt}/{total} -> {h_cnt/total*100:.1f}%")

    # 4. RSI Oversold
    for r in [40, 35, 30, 25]:
        h_cnt = len(hits_df[hits_df['rsi'] <= r])
        f_cnt = len(fails_df[fails_df['rsi'] <= r])
        total = h_cnt + f_cnt
        if total > 0:
            print(f"rsi <= {r}: {h_cnt}/{total} -> {h_cnt/total*100:.1f}%")

    # 10. SPLIT PERSONALITY ANALYSIS
    print("\n" + "="*80)
    print("🎭 SPLIT PERSONALITY ANALYSIS")
    print("="*80)
    
    # Cluster 1: DIP (Mom5 <= -5)
    dip_hits = hits_df[hits_df['mom_5d'] <= -5]
    dip_fails = fails_df[fails_df['mom_5d'] <= -5]
    print(f"\nCluster 1: DIP (Mom5 <= -5)")
    print(f"Hits: {len(dip_hits)} | Fails: {len(dip_fails)}")
    if not dip_hits.empty:
        print("  Top Dip Hits:")
        for _, r in dip_hits.head(5).iterrows():
            print(f"    {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | E:{r['ema_dist']:.1f} | R:{r['rsi']:.1f}")

    # Cluster 2: MOMENTUM (Mom5 >= 5)
    mom_hits = hits_df[hits_df['mom_5d'] >= 5]
    mom_fails = fails_df[fails_df['mom_5d'] >= 5]
    print(f"\nCluster 2: MOMENTUM (Mom5 >= 5)")
    print(f"Hits: {len(mom_hits)} | Fails: {len(mom_fails)}")
    if not mom_hits.empty:
        print("  Top Momentum Hits:")
        for _, r in mom_hits.head(5).iterrows():
            print(f"    {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | E:{r['ema_dist']:.1f} | R:{r['rsi']:.1f}")
            
    # 11. REFINING CLUSTER 1 (DIP)
    print("\n" + "="*80)
    print("🔍 REFINING CLUSTER 1 (DIP)")
    print("="*80)
    
    # Base: Mom5 <= -5
    c1_hits = dip_hits
    c1_fails = dip_fails
    
    # Aggressive Dip
    for m in [-10, -15, -20]:
        h = len(c1_hits[c1_hits['mom_5d'] <= m])
        f = len(c1_fails[c1_fails['mom_5d'] <= m])
        t = h + f
        if t > 0: print(f"Mom5 <= {m}: {h}/{t} -> {h/t*100:.1f}%")

    # RSI Oversold
    print("\n  Testing RSI filters on Dip...")
    for r in [35, 30, 25]:
        h = len(c1_hits[c1_hits['rsi'] <= r])
        f = len(c1_fails[c1_fails['rsi'] <= r])
        t = h + f
        if t > 0: print(f"RSI <= {r}: {h}/{t} -> {h/t*100:.1f}%")
        
    # 12. REFINING CLUSTER 2 (MOMENTUM)
    print("\n" + "="*80)
    print("🔍 REFINING CLUSTER 2 (MOMENTUM)")
    print("="*80)
    
    c2_hits = mom_hits
    c2_fails = mom_fails

    # 13. REFINING BY VOLUME
    print("\n" + "="*80)
    print("🔍 REFINING BY VOLUME")
    print("="*80)
    
    # Analyze Volume for Dip Cluster
    print("\nCluster 1 (Dip) Volume Analysis:")
    for v in [0.5, 0.8, 1.0, 1.5, 2.0]:
        h = len(c1_hits[c1_hits['vol_ratio'] <= v])
        f = len(c1_fails[c1_fails['vol_ratio'] <= v])
        t = h + f
        if t > 0: print(f"  Vol <= {v}: {h}/{t} -> {h/t*100:.1f}%")

    # Analyze Volume for Mom Cluster
    print("\nCluster 2 (Mom) Volume Analysis:")
    for v in [2, 3, 4, 5]:
        h = len(c2_hits[c2_hits['vol_ratio'] >= v])
        f = len(c2_fails[c2_fails['vol_ratio'] >= v])
        t = h + f
        if t > 0: print(f"  Vol >= {v}: {h}/{t} -> {h/t*100:.1f}%")

    # Combo Tests
    print("\nCombo Tests:")
    # Low Vol Dip: Mom5 <= -10 AND Vol <= 0.5
    h = len(hits_df[(hits_df['mom_5d'] <= -10) & (hits_df['vol_ratio'] <= 0.5)])
    f = len(fails_df[(fails_df['mom_5d'] <= -10) & (fails_df['vol_ratio'] <= 0.5)])
    t = h + f
    if t > 0: print(f"Mom5 <= -10 & Vol <= 0.5: {h}/{t} -> {h/t*100:.1f}%")

    # High Vol Mom: Mom5 >= 15 AND Vol >= 3
    h = len(hits_df[(hits_df['mom_5d'] >= 15) & (hits_df['vol_ratio'] >= 3.0)])
    f = len(fails_df[(fails_df['mom_5d'] >= 15) & (fails_df['vol_ratio'] >= 3.0)])
    t = h + f
    if t > 0: print(f"Mom5 >= 15 & Vol >= 3.0: {h}/{t} -> {h/t*100:.1f}%")



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
