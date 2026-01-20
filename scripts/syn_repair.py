"""
SYNUSDT Repair Analysis
=======================
Rule: mom_3d >= 30 AND vol_ratio >= 2
Result: 15 signals, 14 hits, 1 fail (93.3% precision)

Objective: Analyze the 1 failure vs 14 hits.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'SYNUSDT'
    print(f"🔧 {symbol} REPAIR ANALYSIS")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Indicators
    df['mom_3d'] = (df['close'] / df['close'].shift(3) - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    # Extra indicators for filtering
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_dist'] = (df['close'] / df['ema9'] - 1) * 100
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    hits = []
    fails = []
    
    print(f"{'DATE':<12} | {'RES':<4} | {'MOM3':<6} | {'VOL':<5} | {'MOM5':<6} | {'RSI':<5} | {'D_CH':<6}")
    print("-" * 60)
    
    for idx in range(25, len(df)-1):
        row = df.loc[idx]
        
        # Rule
        if row['mom_3d'] >= 30 and row['vol_ratio'] >= 2:
            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            
            res_str = "✅" if is_hit else "❌"
            print(f"{row['datetime'].date()} | {res_str} | {row['mom_3d']:5.1f} | {row['vol_ratio']:4.1f} | {row['mom_5d']:5.1f} | {row['rsi']:4.1f} | {row['daily_ch']:5.1f}")
            
            if is_hit:
                hits.append(row)
            else:
                fails.append(row)
                
    hits_df = pd.DataFrame(hits)
    fails_df = pd.DataFrame(fails)
    
    if not fails_df.empty:
        print("\n" + "="*70)
        print("🔍 FAILURE ANALYSIS")
        print("="*70)
        print("FAIL ROWS:")
        print(fails_df[['datetime', 'mom_3d', 'vol_ratio', 'mom_5d', 'rsi', 'daily_ch']])
        
        # Check thresholds
        fail_val = fails_df.iloc[0]
        
        print("\n💡 POTENTIAL FILTERS:")
        for col in ['mom_3d', 'vol_ratio', 'mom_5d', 'rsi', 'daily_ch']:
             # Eliminate fail based on this column
             # Try > Fail
             passed = len(hits_df[hits_df[col] > fail_val[col]])
             if passed > 0:
                 print(f"  {col} > {fail_val[col]:.2f} -> Removes fail, keeps {passed}/{len(hits)} hits")
             
             # Try < Fail
             passed = len(hits_df[hits_df[col] < fail_val[col]])
             if passed > 0:
                 print(f"  {col} < {fail_val[col]:.2f} -> Removes fail, keeps {passed}/{len(hits)} hits")

if __name__ == "__main__":
    main()
