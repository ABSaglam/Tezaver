
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
    symbol = 'ALGOUSDT'
    print(f"✅ GOLDEN SPLIT VERIFICATION: {symbol}")
    print("="*70)

    # 1. Load Data
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
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
    
    df['daily_ch'] = (df['close'] / df['open'] - 1) * 100
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_dist'] = (df['close'] / df['ema_50'] - 1) * 100

    # 3. Apply Strategy
    signals = []
    
    for idx in range(50, len(df)-1):
        row = df.loc[idx]
        
        # Rule 1: The Golden Dip (Crash Buyer)
        # Deep drops only.
        cond_dip = (
            (row['mom_5d'] <= -15) and
            (row['rsi'] <= 30) and
            (row['vol_ratio'] <= 3.0) and # No absolute panic, but high vol ok
            (row['daily_ch'] <= -5) # Must be a red day crash (counter-intuitive but data says so)
        )
        
        # Rule 2: The Golden Trend (Steady Uptrend)
        # Not a breakout, but a continuation in a strong trend
        cond_trend = (
            (row['mom_5d'] >= 5) and # Positive mom
            (row['ema_dist'] >= 20) and # Strong trend
            (row['vol_ratio'] <= 1.8) and # Quiet accumulation
            (row['rsi'] >= 65) # Strong RSI
        )
        
        if cond_dip or cond_trend:
            next_date = df.loc[idx+1, 'datetime'].date()
            is_hit = next_date in rally_results
            
            res_str = "HIT" if is_hit else "FAIL"
            tier = rally_results[next_date][0] if is_hit else "---"
            
            type_str = "DIP" if cond_dip else "TREND"
            
            signals.append({
                'date': row['datetime'].date(),
                'result': res_str,
                'tier': tier,
                'type': type_str,
                'mom_5d': row['mom_5d'],
                'rsi': row['rsi']
            })
            
            print(f"{row['datetime'].date()} | {res_str} ({tier}) | {type_str} | M5:{row['mom_5d']:.1f} | E:{row['ema_dist']:.1f} | DCH:{row['daily_ch']:.1f}")

    # 4. Summary
    total = len(signals)
    hits = len([s for s in signals if s['result'] == "HIT"])
    dg_hits = len([s for s in signals if s['result'] == "HIT" and s['tier'] in ['DIAMOND', 'GOLD']])
    
    print("\n" + "="*70)
    print(f"📊 SUMMARY: {hits}/{total} signals (DG Hits: {dg_hits})")
    if total > 0:
        print(f"Precision: {hits/total*100:.1f}%")
        
    validation_passed = (total >= 4 and hits/total >= 0.8)
    
    if validation_passed:
        print("\n✅ STRATEGY VERIFIED (>80% Precision)")
    else:
        print("\n❌ STRATEGY FAILED Verification")

if __name__ == "__main__":
    main()
