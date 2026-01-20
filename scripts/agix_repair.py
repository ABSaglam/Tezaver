
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
    symbol = 'AGIXUSDT'
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

    # 3. BLIND SCAN (Find matches first)
    print("\n" + "="*80)
    print("👀 BLIND SCAN: INSPECTING ALL RALLY DAYS")
    print("="*80)
    
    hits = []
    fails = []
    
    # Iterate to find ALL rallies
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        next_date = df.loc[idx+1, 'datetime'].date()
        
        if next_date in rally_results:
            tier = rally_results[next_date][0]
            print(f"{row['datetime'].date()} -> {next_date} ({tier}) | M5:{row['mom_5d']:.1f} | M3:{row['mom_3d']:.1f} | E:{row['ema_dist']:.1f} | DCH:{row['daily_ch']:.1f} | R:{row['rsi']:.1f} | V:{row['vol_ratio']:.1f}")
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

    # 9. RSI DEEP DIVE
    print("\n" + "="*80)
    print("🔍 RSI DEEP DIVE")
    print("="*80)
    
    # 1. RSI Thresholds
    for r in [20, 25, 30, 35, 40]:
        h = len(hits_df[hits_df['rsi'] <= r])
        t = h + len(fails_df[fails_df['rsi'] <= r])
        if t > 0:
            print(f"RSI <= {r}: {h}/{t} -> {h/t*100:.1f}%")
            
    # 2. RSI Bands
    print("\nRSI Bands:")
    ranges = [(20, 30), (30, 40), (40, 50)]
    for low, high in ranges:
        h = len(hits_df[(hits_df['rsi'] >= low) & (hits_df['rsi'] <= high)])
        t = h + len(fails_df[(fails_df['rsi'] >= low) & (fails_df['rsi'] <= high)])
        if t > 0:
            print(f"RSI {low}-{high}: {h}/{t} -> {h/t*100:.1f}%")

    # 3. Combo: Deep Dip (Mom <= -10 & RSI <= 25)
    print("\nDeep Dip Combo:")
    mask = (hits_df['mom_5d'] <= -10) & (hits_df['rsi'] <= 25)
    mask_f = (fails_df['mom_5d'] <= -10) & (fails_df['rsi'] <= 25)
    h = len(hits_df[mask])
    t = h + len(fails_df[mask_f])
    if t > 0:
        print(f"Mom5<=-10 & RSI<=25: {h}/{t} -> {h/t*100:.1f}%")
        
    print("\nForensics for RSI <= 25:")
    hits = hits_df[hits_df['rsi'] <= 25]
    fails = fails_df[fails_df['rsi'] <= 25]
    print("HITS:")
    for _, r in hits.iterrows():
        print(f"  {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | V:{r['vol_ratio']:.1f} | E:{r['ema_dist']:.1f}")
    print("FAILS:")
    for _, r in fails.iterrows():
        print(f"  {r['datetime'].date()} | M5:{r['mom_5d']:.1f} | R:{r['rsi']:.1f} | V:{r['vol_ratio']:.1f} | E:{r['ema_dist']:.1f}")


if __name__ == "__main__":
    main()
