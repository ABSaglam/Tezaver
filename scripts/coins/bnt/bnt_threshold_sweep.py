"""
BNTUSDT Threshold Sweep
=======================
Bancor - OG DeFi
Pattern Discovery:
mom_7d: +7.05% avg (+15411% fark!) -> MEGA MOMENTUM 🚀🚀🚀
mom_5d: +5.96% avg (+5323% fark)
mom_3d: +4.15% avg (+2867% fark)
117 DG Rallies.

BNT, en güçlü momentum profili!
Tüm göstergeler ultra pozitif.

Test:
High Momentum (mom_7d >= 3, 5, 8, 10)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'BNTUSDT'
    print(f"🔬 {symbol} (Bancor) Threshold Sweep - Mega Momentum")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['mom_7d'] = (df_1d['close'] / df_1d['close'].shift(7) - 1) * 100
    
    print("\n" + "="*70)
    print("🔬 BNT Strateji Testleri")
    print("="*70)
    
    # Test 1: Weekly Momentum (mom_7d)
    print("\n📊 Test 1: Weekly Momentum (mom_7d):")
    for thresh in [3, 5, 8, 10, 15]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_7d'] >= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                if next_date in rally_results:
                    tier, gain = rally_results[next_date]
                    is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_7d >= {thresh}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")

    # Test 2: Medium Momentum (mom_5d)
    print("\n📊 Test 2: Medium Momentum (mom_5d):")
    for thresh in [3, 5, 8, 10]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_5d'] >= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                if next_date in rally_results:
                    tier, gain = rally_results[next_date]
                    is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_5d >= {thresh}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")

    # Test 3: Short Momentum (mom_3d)
    print("\n📊 Test 3: Short Momentum (mom_3d):")
    for thresh in [3, 5, 8]:
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
            print(f"  mom_3d >= {thresh}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")

    print("\n✅ Sweep complete!")

if __name__ == "__main__":
    main()
