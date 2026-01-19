"""
AAVE Hybrid Strategy Test
==========================
PATH A: Dip Buying (existing V2)
PATH B: Momentum (new)
Tests combinations to find 100% precision with max signals.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies

def main():
    symbol = 'AAVEUSDT'
    print(f"🔄 Testing {symbol} Hybrid Strategy...")
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'])
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    print("\n" + "="*70)
    print(f"🔬 HYBRID STRATEGY TESTS")
    print("="*70)
    
    # Test different momentum thresholds
    print("\n📊 PATH B (Momentum) Testing:")
    for mom_t in [20, 25, 30]:
        for ema_t in [10, 15, 20]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                
                # Only test momentum path
                if row['mom_5d'] >= mom_t and row['ema_dist'] >= ema_t:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    tier, gain = rally_results.get(next_date, ('NONE', 0.0))
                    is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
            
            if signals:
                hits = sum(signals)
                prec = hits / len(signals) * 100
                if prec >= 90:
                    marker = " ✅" if prec == 100 else " 🔶"
                    print(f"  mom_5d>={mom_t}%, ema>={ema_t}%: {len(signals)} sig, {hits} hit -> {prec:.0f}%{marker}")
    
    # Test HYBRID (PATH A OR PATH B)
    print("\n📊 HYBRID (Dip OR Momentum) Testing:")
    
    test_configs = [
        # (dip_daily, dip_mom3d, momentum_mom5d, momentum_ema)
        (-15, -20, 25, 15),
        (-15, -20, 20, 15),
        (-15, -20, 20, 20),
    ]
    
    for dip_d, dip_m3, mom_m5, mom_ema in test_configs:
        signals = []
        path_a_count = 0
        path_b_count = 0
        
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            
            # PATH A: Dip Buying
            path_a = (row['daily_ch'] <= dip_d and row['mom_3d'] <= dip_m3)
            
            # PATH B: Momentum
            path_b = (row['mom_5d'] >= mom_m5 and row['ema_dist'] >= mom_ema)
            
            if path_a or path_b:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                tier, gain = rally_results.get(next_date, ('NONE', 0.0))
                is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                signals.append(is_hit)
                
                if path_a: path_a_count += 1
                if path_b: path_b_count += 1
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else " 🔶"
            print(f"  Dip({dip_d},{dip_m3}) OR Mom({mom_m5},{mom_ema}): {len(signals)} sig ({path_a_count}A+{path_b_count}B), {hits} hit -> {prec:.0f}%{marker}")
    
    print("\n✅ Testing complete!")

if __name__ == "__main__":
    main()
