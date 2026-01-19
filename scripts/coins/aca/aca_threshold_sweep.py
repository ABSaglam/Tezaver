"""
ACAUSDT Threshold Sweep
========================
Tests mom_3d thresholds (strongest discriminator: +771%)
Train data only (2023-2025), 2026 held out for testing.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ACAUSDT'
    print(f"🔄 Loading {symbol} (train data only)...")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    print(f"✓ {len(rally_results)} rallies (2023-2025)")
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    print("✓ Ready")
    
    print("\n" + "="*70)
    print(f"🔬 {symbol} THRESHOLD SWEEP (TRAIN: 2023-2025)")
    print("="*70)
    
    # mom_3d sweep
    print("\n📊 mom_3d Sweep:")
    for thresh in [15, 20, 25, 30, 35, 40]:
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
            print(f"  mom_3d >= {thresh}%: {len(signals)} signals, {hits} hits -> {prec:.1f}%{marker}")
    
    # mom_3d + vol combined
    print("\n📊 mom_3d + vol_ratio Combined:")
    for m in [15, 20, 25]:
        for v in [2.0, 2.5, 3.0]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['mom_3d'] >= m and row['vol_ratio'] >= v:
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
                    print(f"  mom_3d>={m}%, vol>={v}x: {len(signals)} sig, {hits} hit -> {prec:.1f}%{marker}")
    
    print("\n✅ Sweep complete!")
    print("📌 2026 data held out for testing")

if __name__ == "__main__":
    main()
