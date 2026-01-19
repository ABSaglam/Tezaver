"""
AGLDUSDT Threshold Sweep
=========================
Gaming token - mom_5d en güçlü (+1896%)
Karışık dağılım var: 17 pozitif, 11 negatif

Test: Pure momentum ne kadar güçlü?
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'AGLDUSDT'
    print(f"🔬 {symbol} (Gaming) Threshold Sweep")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    print("\n" + "="*70)
    print("🔬 Gaming Token Stratejileri")
    print("="*70)
    
    # Test 1: Pure mom_5d
    print("\n📊 Test 1: Pure Momentum (mom_5d):")
    for thresh in [10, 15, 20, 25]:
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
    
    # Test 2: Combined mom_5d + ema_dist
    print("\n📊 Test 2: Momentum + EMA Distance:")
    for m in [10, 15]:
        for e in [5, 10]:
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
    
    print("\n✅ Sweep complete!")

if __name__ == "__main__":
    main()
