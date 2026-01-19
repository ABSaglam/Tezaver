"""
ACEUSDT Threshold Sweep
========================
Tests thresholds on strongest discriminators.
Train: 2023-2025 | Test: 2026 held out
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ACEUSDT'
    print(f"🔄 {symbol} Threshold Sweep (train data)...")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    print("\n" + "="*70)
    print(f"🔬 THRESHOLD SWEEP (TRAIN: 2023-2025)")
    print("="*70)
    
    # Test mom_3d + daily_ch combo (two strongest)
    print("\n📊 mom_3d + daily_ch Combined:")
    for m in [5, 10, 15, 20]:
        for d in [5, 10, 15]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['mom_3d'] >= m and row['daily_ch'] >= d:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    if next_date in rally_results:
                        tier, gain = rally_results[next_date]
                        is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                        signals.append(is_hit)
            
            if signals:
                hits = sum(signals)
                prec = hits / len(signals) * 100
                if prec >= 90:
                    marker = " ✅" if prec == 100 else " 🔶"
                    print(f"  mom_3d>={m}%, daily>={d}%: {len(signals)} sig, {hits} hit -> {prec:.0f}%{marker}")
    
    # Test single mom_3d
    print("\n📊 mom_3d Alone:")
    for thresh in [10, 15, 20, 25]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_3d'] >= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                if next_date in rally_results:
                    tier, gain = rally_results[next_date]
                    is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_3d >= {thresh}%: {len(signals)} sig, {hits} hit -> {prec:.0f}%{marker}")
    
    print("\n✅ Done!")

if __name__ == "__main__":
    main()
