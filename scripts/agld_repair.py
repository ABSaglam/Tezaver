
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
    symbol = 'AGLDUSDT'
    print(f"🔧 {symbol} REPAIR ANALYSIS")
    print("="*70)

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

    # 3. BLIND SCAN (DIAMOND/GOLD ONLY)
    print("\n" + "="*80)
    print("👀 BLIND SCAN: DIAMOND & GOLD ONLY")
    print("="*80)
    
    hits = []
    fails = []
    
    # Iterate to find rallies
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        next_date = df.loc[idx+1, 'datetime'].date()
        
        if next_date in rally_results:
            tier = rally_results[next_date][0]
            # Only track DG for "Hits", treat Silver as noise (ignore or fail?)
            # Let's treat Silver as Fail for now to find "Big Win" signals? 
            # Or just analyze DG specifically.
            if tier in ['DIAMOND', 'GOLD']:
                print(f"{row['datetime'].date()} -> {next_date} ({tier}) | M5:{row['mom_5d']:.1f} | M3:{row['mom_3d']:.1f} | E:{row['ema_dist']:.1f} | DCH:{row['daily_ch']:.1f} | R:{row['rsi']:.1f} | V:{row['vol_ratio']:.1f}")
                hits.append(row)
            else:
                # Silvers are failures for the purpose of finding a "Big Win" strategy
                fails.append(row)
        else:
            fails.append(row)

    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    if hits_df.empty:
        print("❌ NO DIAMOND/GOLD RALLIES FOUND!")
        return
        
    print(f"\nAnalyzing {len(hits_df)} Big Wins (Diamond/Gold) vs {len(fails_df)} Fails/Silvers")

    # 4. Compare Averages
    print("\n" + "="*70)
    print(f"🔍 COMPARISON (DG Hits vs Rest)")
    print("="*70)
    print(f"{'Indicator':<10} | {'Hits Avg':<8} | {'Fails Avg':<9} | {'Diff':<8}")
    print("-" * 50)
    
    indicators = ['mom_3d', 'mom_5d', 'mom_7d', 'vol_ratio', 'rsi', 'daily_ch', 'ema_dist']
    
    for ind in indicators:
        h_avg = hits_df[ind].mean() if not hits_df.empty else 0
        f_avg = fails_df[ind].mean() if not fails_df.empty else 0
        diff = abs(h_avg - f_avg)
        print(f"{ind:<10} | {h_avg:>8.2f} | {f_avg:>9.2f} | {diff:>8.2f}")

    # 5. HYPOTHESIS TESTING
    print("\n" + "="*80)
    print("🧪 HYPOTHESIS TESTING")
    print("="*80)
    
    # Momentum (High)
    print("Momentum Check (M5 >= 10):")
    h = len(hits_df[hits_df['mom_5d'] >= 10])
    t = h + len(fails_df[fails_df['mom_5d'] >= 10])
    print(f"  M5 >= 10: {h}/{t} -> {h/t*100:.1f}%")

    # Dip (Low)
    print("Dip Check (M5 <= -10):")
    h = len(hits_df[hits_df['mom_5d'] <= -10])
    t = h + len(fails_df[fails_df['mom_5d'] <= -10])
    print(f"  M5 <= -10: {h}/{t} -> {h/t*100:.1f}%")
    
    # 6. SPLIT PERSONALITY ANALYSIS (DG Only)
    print("\n" + "="*80)
    print("🎭 SPLIT PERSONALITY ANALYSIS (DIAMOND/GOLD)")
    print("="*80)
    
    # Cluster 1: DIP (Mom5 <= -5)
    dip_hits = hits_df[hits_df['mom_5d'] <= -5]
    dip_fails = fails_df[fails_df['mom_5d'] <= -5] # Note: Fails include Silvers
    print(f"\nCluster 1: DIP (Mom5 <= -5)")
    print(f"Hits: {len(dip_hits)} | Fails: {len(dip_fails)}")
    if not dip_hits.empty:
        print("  Top Dip Hits:")
        for _, r in dip_hits.head(10).iterrows():
            print(f"    {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | E:{r['ema_dist']:.1f} | R:{r['rsi']:.1f} | V:{r['vol_ratio']:.1f}")

    # Cluster 2: MOMENTUM (Mom5 >= 5)
    mom_hits = hits_df[hits_df['mom_5d'] >= 5]
    mom_fails = fails_df[fails_df['mom_5d'] >= 5]
    print(f"\nCluster 2: MOMENTUM (Mom5 >= 5)")
    print(f"Hits: {len(mom_hits)} | Fails: {len(mom_fails)}")
    if not mom_hits.empty:
        print("  Top Momentum Hits:")
        for _, r in mom_hits.head(10).iterrows():
            print(f"    {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | E:{r['ema_dist']:.1f} | R:{r['rsi']:.1f} | V:{r['vol_ratio']:.1f}")

    # 7. REFINEMENT - MOMENTUM (Can we cap it?)
    print("\nRefining Momentum:")
    # Try high momentum thresholds
    for m in [10, 20, 30, 40]:
        h = len(mom_hits[mom_hits['mom_5d'] >= m])
        f = len(mom_fails[mom_fails['mom_5d'] >= m])
        t = h + f
        if t > 0: print(f"  Mom5 >= {m}: {h}/{t} -> {h/t*100:.1f}%")
        
    # 8. REFINEMENT - DIP (Deep or Shallow?)
    print("\nRefining Dip:")
    for m in [-10, -15, -20]:
        h = len(dip_hits[dip_hits['mom_5d'] <= m])
        f = len(dip_fails[dip_fails['mom_5d'] <= m])
        t = h + f
        if t > 0: print(f"  Mom5 <= {m}: {h}/{t} -> {h/t*100:.1f}%")

if __name__ == "__main__":
    main()
