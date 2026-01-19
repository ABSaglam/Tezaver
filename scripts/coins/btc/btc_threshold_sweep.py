"""
BTCUSDT Threshold Sweep
=======================
Bitcoin - THE Major Coin
Pattern Discovery:
ema_dist: -0.28% avg (-153% fark) -> EMA Altında
mom_7d: -0.52% avg (-146% fark) -> Haftalık Dip
mom_5d: -0.28% avg (-135% fark) -> Orta Vadeli Dip
27 DG Rallies (Çok Seçici!)

BTC, BNB gibi "Dip Buyer" profili.
Blue Chip Paradigm: Major coinlerde zayıfken al.

Test:
Dip (mom_7d <= 0, -2, -5)
EMA Dip (ema_dist <= 0, -2)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'BTCUSDT'
    print(f"🔬 {symbol} (Bitcoin) Threshold Sweep - Blue Chip Dip")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['mom_7d'] = (df_1d['close'] / df_1d['close'].shift(7) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    
    print("\n" + "="*70)
    print("🔬 BTC Strateji Testleri")
    print("="*70)
    
    # Test 1: Weekly Momentum Dip
    print("\n📊 Test 1: Weekly Momentum Dip (mom_7d):")
    for thresh in [0, -2, -5, -8]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_7d'] <= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                if next_date in rally_results:
                    tier, gain = rally_results[next_date]
                    is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_7d <= {thresh}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")

    # Test 2: EMA Distance Dip
    print("\n📊 Test 2: EMA Distance Dip (ema_dist):")
    for thresh in [0, -1, -2, -3]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['ema_dist'] <= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                if next_date in rally_results:
                    tier, gain = rally_results[next_date]
                    is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  ema_dist <= {thresh}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")

    # Test 3: Daily Dip
    print("\n📊 Test 3: Daily Dip (daily_ch):")
    for thresh in [0, -1, -2, -3]:
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

    print("\n✅ Sweep complete!")

if __name__ == "__main__":
    main()
