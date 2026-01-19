"""
ACMUSDT Threshold Sweep
========================
ACM'nin karışık pattern'ini çöz:
- daily_ch median negatif ama ortalama pozitif
- Hem pozitif hem negatif rally günleri var

Hipotez: İki farklı rally tipi olabilir?
1. Momentum rally (pozitif mom_3d/5d)
2. Dip-buying rally (negatif daily_ch)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ACMUSDT'
    print(f"🔬 {symbol} Threshold Sweep - Gizemi Çöz")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    
    print("\n" + "="*70)
    print("🔬 STRATEJİ TESTLERİ")
    print("="*70)
    
    # Test 1: Pure momentum (mom_3d)
    print("\n📊 Test 1: Pure Momentum (mom_3d):")
    for thresh in [5, 10, 15, 20, 25]:
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
    
    # Test 2: Dip-buying (negative daily_ch)
    print("\n📊 Test 2: Dip-Buying (daily_ch negatif):")
    for thresh in [-15, -10, -5, -3]:
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
    
    # Test 3: Hybrid - momentum YA DA dip
    print("\n📊 Test 3: Hybrid (Momentum VEYA Dip):")
    for m_thresh in [15, 20]:
        for d_thresh in [-5, -8]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                # Momentum VEYA Dip
                if row['mom_3d'] >= m_thresh or row['daily_ch'] <= d_thresh:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    if next_date in rally_results:
                        tier, gain = rally_results[next_date]
                        is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                        signals.append(is_hit)
            
            if signals:
                hits = sum(signals)
                prec = hits / len(signals) * 100
                if prec >= 95:
                    marker = " ✅" if prec == 100 else " 🔶"
                    print(f"  mom_3d>={m_thresh}% OR daily<={d_thresh}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")
    
    # Test 4: Combined AND logic
    print("\n📊 Test 4: Combined (mom_5d AND ema_dist):")
    for m in [10, 15, 20]:
        for e in [5, 10, 15]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['mom_5d'] >= m and row['ema_dist'] >= e:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    if next_date in rally_results:
                        tier, gain = rally_results[next_date]
                        is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                        signals.append(is_hit)
            
            if signals:
                hits = sum(signals)
                prec = hits / len(signals) * 100
                if prec >= 95:
                    marker = " ✅" if prec == 100 else " 🔶"
                    print(f"  mom_5d>={m}% AND ema>={e}%: {len(signals)} sinyal, {hits} hit -> {prec:.0f}%{marker}")
    
    print("\n✅ Threshold sweep complete!")

if __name__ == "__main__":
    main()
