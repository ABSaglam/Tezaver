"""
ACHUSDT Unique Pattern Discovery
=================================
Discovers ACH's unique rally characteristics from scratch.
Train data: 2023-2025 | Test holdout: 2026
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ACHUSDT'
    print(f"🔄 Loading {symbol}...")
    print(f"⚠️  Train: 2023-2025 | Test: 2026 (held out)")
    
    from datetime import timedelta
    rally_signal_dates = set()
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'], train_only=True)
    
    for rally_date in rally_results.keys():
        signal_date = rally_date - timedelta(days=1)
        rally_signal_dates.add(signal_date)
    
    print(f"✓ {len(rally_results)} DG rallies (train)")
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    print(f"✓ {len(df_1d)} candles")
    
    print("🔄 Calculating indicators...")
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['rsi'] = df_1d['close'].diff().apply(lambda x: max(x, 0)).rolling(14).mean() / df_1d['close'].diff().abs().rolling(14).mean() * 100
    print("✓ Done")
    
    rally_features = []
    non_rally_features = []
    
    print("🔄 Analyzing patterns...")
    for idx in range(25, len(df_1d)):
        row = df_1d.loc[idx]
        sig_date = row['datetime'].date()
        
        entry = {
            'ema_dist': row['ema_dist'],
            'daily_ch': row['daily_ch'],
            'vol_ratio': row['vol_ratio'],
            'mom_5d': row['mom_5d'],
            'mom_3d': row['mom_3d'],
            'rsi': row['rsi']
        }
        
        if sig_date in rally_signal_dates:
            rally_features.append(entry)
        else:
            non_rally_features.append(entry)
    
    rally_df = pd.DataFrame(rally_features)
    non_rally_df = pd.DataFrame(non_rally_features)
    
    print("\n" + "="*70)
    print(f"📊 ACHUSDT PATTERN DISCOVERY (TRAIN: 2023-2025)")
    print(f"Rally Days: {len(rally_df)} | Non-Rally Days: {len(non_rally_df)}")
    print("="*70)
    
    print("\n🎯 RALLY DAYS Statistics:")
    print(rally_df.describe().loc[['mean', '50%']])
    
    print("\n❌ NON-RALLY DAYS Statistics:")
    print(non_rally_df.describe().loc[['mean', '50%']])
    
    print("\n" + "="*60)
    print("🔍 DISCRIMINATING FEATURES")
    print("="*60)
    
    for col in ['ema_dist', 'daily_ch', 'vol_ratio', 'mom_5d', 'mom_3d', 'rsi']:
        r_mean = rally_df[col].mean()
        nr_mean = non_rally_df[col].mean()
        diff = ((r_mean - nr_mean) / abs(nr_mean) * 100) if nr_mean != 0 else 0
        print(f"{col:12s}: Rally={r_mean:7.2f} vs NonRally={nr_mean:7.2f} (Diff: {diff:+7.0f}%)")
    
    print("\n✅ Complete!")
    print("📌 2026 test data held out")

if __name__ == "__main__":
    main()
