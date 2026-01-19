"""
AAVE Hybrid Strategy Development
=================================
Analyzes the 9 missed rallies to find momentum pattern.
Uses safe database helper to prevent freezing.
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

# Safe database helper
sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies

def main():
    symbol = 'AAVEUSDT'
    print(f"🔄 Analyzing {symbol} missed rallies...")
    
    # SAFE: Auto-closes connection
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'])
    print(f"✓ {len(rally_results)} DG rallies")
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    
    # Calculate indicators
    print("🔄 Calculating indicators...")
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    print("✓ Ready")
    
    # Identify caught vs missed rallies
    caught_rallies = []
    missed_rallies = []
    
    for idx in range(25, len(df_1d)):
        row = df_1d.loc[idx]
        signal_date = row['datetime'].date()
        
        if signal_date in rally_results:
            tier, gain = rally_results[signal_date]
            entry = {
                'date': signal_date,
                'tier': tier,
                'gain': gain,
                'daily': row['daily_ch'],
                'mom_3d': row['mom_3d'],
                'mom_5d': row['mom_5d'],
                'ema': row['ema_dist'],
                'vol': row['vol_ratio']
            }
            
            # Check if current V2 strategy would catch it
            is_caught = (row['daily_ch'] <= -15 and row['mom_3d'] <= -20)
            
            if is_caught:
                caught_rallies.append(entry)
            else:
                missed_rallies.append(entry)
    
    print("\n" + "="*70)
    print(f"📊 AAVE RALLY ANALYSIS")
    print("="*70)
    print(f"Caught by V2 (Dip): {len(caught_rallies)}")
    print(f"Missed by V2: {len(missed_rallies)}")
    
    if caught_rallies:
        print("\n✅ CAUGHT RALLIES (Dip Buying Pattern):")
        for r in caught_rallies:
            print(f"  {r['date']}: {r['tier']}, daily={r['daily']:.1f}%, mom_3d={r['mom_3d']:.1f}%, mom_5d={r['mom_5d']:.1f}%, ema={r['ema']:.1f}%")
    
    if missed_rallies:
        print("\n❌ MISSED RALLIES (Need Momentum Pattern?):")
        for r in missed_rallies:
            print(f"  {r['date']}: {r['tier']}, daily={r['daily']:.1f}%, mom_3d={r['mom_3d']:.1f}%, mom_5d={r['mom_5d']:.1f}%, ema={r['ema']:.1f}%")
        
        # Analyze missed rally characteristics
        missed_df = pd.DataFrame(missed_rallies)
        print("\n" + "="*60)
        print("🔍 MISSED RALLY CHARACTERISTICS:")
        print("="*60)
        for col in ['daily', 'mom_3d', 'mom_5d', 'ema', 'vol']:
            print(f"{col:10s}: min={missed_df[col].min():6.1f}, max={missed_df[col].max():6.1f}, avg={missed_df[col].mean():6.1f}")
        
        # Test momentum thresholds
        print("\n📊 Testing Momentum Thresholds on Missed Rallies:")
        
        # mom_5d positive threshold
        for thresh in [5, 10, 15, 20]:
            count = len(missed_df[missed_df['mom_5d'] >= thresh])
            if count > 0:
                print(f"  mom_5d >= {thresh}%: {count} rallies")
        
        # ema_dist positive threshold
        for thresh in [3, 5, 10, 15]:
            count = len(missed_df[missed_df['ema'] >= thresh])
            if count > 0:
                print(f"  ema_dist >= {thresh}%: {count} rallies")
    
    print("\n✅ Analysis complete!")

if __name__ == "__main__":
    main()
