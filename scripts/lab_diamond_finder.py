import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

def find_diamonds(symbol):
    path_15m = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
    if not os.path.exists(path_15m): return []
    
    try:
        df = pd.read_parquet(path_15m)
        if df.empty: return []
        if 'datetime' in df.columns:
            df.set_index('datetime', inplace=True)
            df.index = pd.to_datetime(df.index)
    except:
        return []
        
    df['vol_ma'] = df['volume'].rolling(50).mean()
    
    results = []
    
    # Range: 2025-2026
    df_range = df[df.index.year >= 2025]
    
    for i in range(50, len(df_range) - 193):
        vol = df_range['volume'].iloc[i]
        avg_vol = df_range['vol_ma'].iloc[i]
        
        # T0: Massive Volume Spike (Relative to local context)
        if avg_vol > 0 and vol > 5.0 * avg_vol:
            t0_time = df_range.index[i]
            t0_close = df_range['close'].iloc[i]
            
            # Check next 48 hours (192 bars)
            future = df_range.iloc[i+1 : i+193]
            if future.empty: continue
            
            max_p = future['high'].max()
            gain = (max_p / t0_close - 1) * 100
            
            if gain >= 50.0:  # Diamond standard
                results.append({
                    'time': t0_time,
                    'gain': gain,
                    't0_vol_ratio': vol / avg_vol
                })
                
    return results

if __name__ == "__main__":
    all_symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    # Filter out non-USDT or other junk
    all_symbols = [s for s in all_symbols if s.endswith("USDT")]
    
    all_diamonds = []
    print(f"Scanning {len(all_symbols)} symbols for Diamond Rallies...")
    
    for s in all_symbols:
        ds = find_diamonds(s)
        if ds:
            print(f"Found {len(ds)} in {s}")
        for d in ds:
            d['symbol'] = s
            all_diamonds.append(d)
    
    df_res = pd.DataFrame(all_diamonds)
    if not df_res.empty:
        df_res.sort_values(by='gain', ascending=False, inplace=True)
        print("\n💎 MASTER RALLY SAMPLES (Diamond >50%) 💎")
        print(df_res.head(50).to_string())
        df_res.to_csv("master_rallies_all.csv")
    else:
        print("No Master Rallies found in the entire dataset.")
