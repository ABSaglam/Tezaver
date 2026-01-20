
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
    symbol = 'ALICEUSDT'
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
    
    # Shadow
    df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
    df['range'] = df['high'] - df['low']
    df['shadow_ratio'] = df['lower_shadow'] / df['range']

    # 3. BLIND SCAN
    print("\n" + "="*80)
    print("👀 BLIND SCAN: INSPECTING ALL RALLY DAYS")
    print("="*80)
    
    hits = []
    fails = []
    
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        next_date = df.loc[idx+1, 'datetime'].date()
        
        if next_date in rally_results:
            tier = rally_results[next_date][0]
            print(f"{row['datetime'].date()} -> {next_date} ({tier}) | M5:{row['mom_5d']:.1f} | R:{row['rsi']:.1f} | S:{row['shadow_ratio']:.2f} | V:{row['vol_ratio']:.1f}")
            hits.append(row)
        else:
            fails.append(row)

    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    if hits_df.empty:
        print("❌ NO RALLIES FOUND!")
        return

    # 4. Averages
    print("\n" + "="*70)
    print(f"🔍 COMPARISON (Averages)")
    print("="*70)
    indicators = ['mom_5d', 'vol_ratio', 'rsi', 'shadow_ratio', 'ema_dist']
    
    for ind in indicators:
        h_avg = hits_df[ind].mean() if not hits_df.empty else 0
        f_avg = fails_df[ind].mean() if not fails_df.empty else 0
        diff = h_avg - f_avg
        print(f"{ind:<12} | {h_avg:>8.2f} | {f_avg:>8.2f} | {diff:>8.2f}")

    # 5. INITIAL SWEEP (Brute Lite)
    print("\n" + "="*80)
    print("🧹 INITIAL SWEEP")
    
    # Check Dip
    h = len(hits_df[hits_df['mom_5d'] <= -10])
    t = h + len(fails_df[fails_df['mom_5d'] <= -10])
    if t > 0: print(f"DIP (M5<=-10): {h}/{t} ({h/t*100:.1f}%)")
    
    # Check Mom
    h = len(hits_df[hits_df['mom_5d'] >= 10])
    t = h + len(fails_df[fails_df['mom_5d'] >= 10])
    if t > 0: print(f"MOM (M5>=10):  {h}/{t} ({h/t*100:.1f}%)")
    
    # Check Pinbar
    h = len(hits_df[hits_df['shadow_ratio'] >= 0.3])
    t = h + len(fails_df[fails_df['shadow_ratio'] >= 0.3])
    if t > 0: print(f"PIN (S>=0.3):  {h}/{t} ({h/t*100:.1f}%)")

if __name__ == "__main__":
    main()
