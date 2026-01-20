"""
C98USDT Threshold Sweep - DOĞRU VERSİYON
=========================================
Tüm sinyalleri sayarak gerçek precision hesaplıyoruz.
%100 precision bulmak için farklı eşikler deniyoruz.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'C98USDT'
    print(f"🔬 {symbol} - GERÇEK Threshold Sweep")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['mom_7d'] = (df_1d['close'] / df_1d['close'].shift(7) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    
    print("\n📊 Test 1: mom_7d eşikleri:")
    print("-" * 70)
    for thresh in [1, 2, 3, 5, 8, 10]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_7d'] >= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                is_rally = next_date in rally_results
                signals.append(is_rally)
        
        if signals:
            hits = sum(signals)
            total = len(signals)
            prec = hits / total * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_7d >= {thresh}%: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")
    
    print("\n📊 Test 2: mom_5d eşikleri:")
    print("-" * 70)
    for thresh in [1, 2, 3, 5, 8]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_5d'] >= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                is_rally = next_date in rally_results
                signals.append(is_rally)
        
        if signals:
            hits = sum(signals)
            total = len(signals)
            prec = hits / total * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_5d >= {thresh}%: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")
    
    print("\n📊 Test 3: mom_3d eşikleri:")
    print("-" * 70)
    for thresh in [1, 2, 3, 5, 8]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_3d'] >= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                is_rally = next_date in rally_results
                signals.append(is_rally)
        
        if signals:
            hits = sum(signals)
            total = len(signals)
            prec = hits / total * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_3d >= {thresh}%: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")
    
    print("\n📊 Test 4: Hybrid strategies:")
    print("-" * 70)
    
    # mom_7d AND ema_dist
    for m7 in [3, 5, 8]:
        for ema in [0, 2, 5]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['mom_7d'] >= m7 and row['ema_dist'] >= ema:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    is_rally = next_date in rally_results
                    signals.append(is_rally)
            
            if signals:
                hits = sum(signals)
                total = len(signals)
                prec = hits / total * 100
                marker = " ✅" if prec == 100 else ""
                print(f"  mom_7d>={m7}% & ema_dist>={ema}%: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")

    print("\n✅ Sweep complete!")

if __name__ == "__main__":
    main()
