"""
AXSUSDT Threshold Sweep
=======================
Axie Infinity - GameFi
Pattern Discovery:
daily_ch: -1.09% avg (Negatif) -> Günlük Düşüşte Al? 📉
mom_3d: -0.76% avg (Negatif)
mom_7d: Nötr (-0.76%)
151 DG Rallies (Beklenenden çok daha aktif! 9 değilmiş.)

AXS, günlük kırmızı mum yaktığında rally başlatıyor gibi duruyor.
Test:
Dip Buying Stratejileri (daily_ch <= -X)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'AXSUSDT'
    print(f"🔬 {symbol} (Axie) Threshold Sweep - Daily Dip")
    
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
    print("🔬 AXS Strateji Testleri")
    print("="*70)
    
    # Test 1: Daily Dip (daily_ch - Pattern Lideri)
    print("\n📊 Test 1: Daily Dip (daily_ch):")
    for thresh in [-2, -3, -5, -8, -10]:
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

    # Test 2: Weekly Dip (mom_7d)
    print("\n📊 Test 2: Weekly Dip (mom_7d):")
    for thresh in [-2, -3, -5, -8]:
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

    # Test 3: Short Dip (mom_3d)
    print("\n📊 Test 3: Short Dip (mom_3d):")
    for thresh in [-2, -3, -5, -8]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_3d'] <= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                if next_date in rally_results:
                    tier, gain = rally_results[next_date]
                    is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_3d <= {thresh}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")

    print("\n✅ Sweep complete!")

if __name__ == "__main__":
    main()
