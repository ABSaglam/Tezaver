"""
BLURUSDT Threshold Sweep
========================
Blur - NFT Marketplace
Pattern Discovery:
daily_ch: -0.55% avg (-261% fark) -> Derin Günlük Dip
mom_3d: -1.20% avg (-120% fark) -> Kısa Vade Düşüş
166 DG Rallies.

BLUR, genel olarak düşüş trendinde (NFT bear).
Ama en derin düştüğü noktada rally başlıyor.

Test:
Deep Dip (daily_ch <= -1, -2, -3)
Mom Dip (mom_3d <= -2, -3, -5)
Mom_7d Dip
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'BLURUSDT'
    print(f"🔬 {symbol} (Blur) Threshold Sweep - Oversold Bounce")
    
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
    print("🔬 BLUR Strateji Testleri")
    print("="*70)
    
    # Test 1: Daily Dip
    print("\n📊 Test 1: Daily Dip (daily_ch):")
    for thresh in [-1, -2, -3, -5]:
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

    # Test 2: Short Momentum Dip (mom_3d)
    print("\n📊 Test 2: Short Momentum Dip (mom_3d):")
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

    # Test 3: Weekly Momentum Dip (mom_7d)
    print("\n📊 Test 3: Weekly Momentum Dip (mom_7d):")
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

    print("\n✅ Sweep complete!")

if __name__ == "__main__":
    main()
