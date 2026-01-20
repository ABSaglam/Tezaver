
import sys
import os
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

# Add scripts to path for db_helper
sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'AGIXUSDT'
    print(f"✅ FINAL VERIFICATION: {symbol}")
    print("="*70)

    # 1. Load Data
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Filter 2023-2025 (Train)
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # 2. Indicators
    df['mom_5d'] = (df['close'] / df['close'].shift(5) - 1) * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Shadows
    df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
    df['range'] = df['high'] - df['low']
    df['shadow_ratio'] = df['lower_shadow'] / df['range']

    # 3. Apply Strategy
    signals = []
    
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        
        # Rule: Pinbar at 20
        # Mom5 <= -10 AND 20 <= RSI <= 23 AND Shadow >= 0.25    
        cond = (
            (row['mom_5d'] <= -10) and
            (row['rsi'] >= 20) and (row['rsi'] <= 23) and
            (row['shadow_ratio'] >= 0.25)
        )
        
        if cond:
            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            
            res_str = "HIT" if is_hit else "FAIL"
            tier = rally_results[next_date][0] if is_hit else "---"
            
            signals.append({
                'date': row['datetime'].date(),
                'result': res_str,
                'tier': tier,
                'mom_5d': row['mom_5d'],
                'rsi': row['rsi'],
                'shadow': row['shadow_ratio']
            })
            
            print(f"{row['datetime'].date()} | {res_str} ({tier}) | M5:{row['mom_5d']:.1f} | R:{row['rsi']:.1f} | S:{row['shadow_ratio']:.2f}")

    # 4. Summary
    total = len(signals)
    hits = len([s for s in signals if s['result'] == "HIT"])
    
    print("\n" + "="*70)
    print(f"📊 SUMMARY: {hits}/{total} signals")
    if total > 0:
        print(f"Precision: {hits/total*100:.1f}%")
        
    # Validation
    if total >= 2 and hits == total:
        print("\n✅ STRATEGY VERIFIED (100% Precision)")
    else:
        print("\n❌ STRATEGY FAILED Verification")

if __name__ == "__main__":
    main()
