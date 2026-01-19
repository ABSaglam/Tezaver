"""
ARUSDT Threshold Sweep
=======================
Arweave - Storage
Pattern Discovery:
mom_7d: +13.18% avg (+2745% fark) -> Güçlü Trend! 🚀
mom_5d: +7.15% avg (+1930% fark)
daily_ch: -2.03% avg (-2153% fark) -> Düzeltme? 📉

Bu bir "Pullback" formasyonu olabilir.
Haftalık trend yukarıda (+13%), ama günlük mum kırmızı (-2%).
Yükselen trendde alım fırsatı.

Test:
1. Pure Momentum (mom_7d > 5)
2. Pure Dip (daily_ch < -2)
3. Hybrid (mom_7d > 5 AND daily_ch < 0)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ARUSDT'
    print(f"🔬 {symbol} (Arweave) Threshold Sweep - Pullback Focus")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['mom_7d'] = (df_1d['close'] / df_1d['close'].shift(7) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    
    print("\n" + "="*70)
    print("🔬 AR Strateji Testleri")
    print("="*70)
    
    # Test 1: Pure Momentum (mom_7d)
    print("\n📊 Test 1: Pure Momentum (mom_7d):")
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

    # Test 2: Pure Dip (daily_ch)
    print("\n📊 Test 2: Pure Dip (daily_ch):")
    for thresh in [-2, -3, -5]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['daily_ch'] <= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                if next_date in rally_results:
                    tier, gain = rally_results[next_date]
                    is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  daily_ch <= {thresh}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")

    # Test 3: Hybrid (Pullback) -> mom_7d > X AND daily_ch < Y
    print("\n📊 Test 3: Hybrid Pullback (Trend + Dip):")
    hybrids = [
        (5, 0), (5, -2), (5, -3),
        (10, 0), (10, -2), (10, -3),
        (3, 0), (3, -2)
    ]
    for m_thresh, d_thresh in hybrids:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_7d'] >= m_thresh and row['daily_ch'] <= d_thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                if next_date in rally_results:
                    tier, gain = rally_results[next_date]
                    is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_7d >= {m_thresh}% AND daily_ch <= {d_thresh}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")

    print("\n✅ Sweep complete!")

if __name__ == "__main__":
    main()
