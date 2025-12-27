
import pandas as pd
import numpy as np
from pathlib import Path

def run_impulse_scan():
    symbol = "ADAUSDT"
    print(f"⚡ HIT & RUN SCANNER: {symbol}")
    print("Definition: >20% Gain in <4 Hours (16 Bars)")
    
    path = Path(f"coin_cells/{symbol}/data/history_15m.parquet")
    if not path.exists(): return
    df = pd.read_parquet(path)
    
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.sort_values('open_time').reset_index(drop=True)
    
    # Logic: Rolling 16-bar Max Gain
    # For every bar, look ahead 16 bars.
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=16) 
    df['impulse_max'] = df['close'].rolling(window=indexer).max()
    df['impulse_gain'] = (df['impulse_max'] - df['close']) / df['close'] * 100
    
    # Filter
    impulses = df[df['impulse_gain'] > 20.0].copy()
    
    # Deduplicate (keep only the start of the burst)
    results = []
    last_idx = -100
    
    for idx in impulses.index:
        if idx - last_idx < 16: continue # Skip overlapping
        last_idx = idx
        
        row = df.loc[idx]
        
        # Find exactly WHEN the max hit (to check speed)
        future = df.loc[idx:idx+15]
        peak_idx = future['close'].idxmax()
        bars_taken = peak_idx - idx
        
        results.append({
            'start_time': row['open_time'],
            'gain': row['impulse_gain'],
            'bars': bars_taken,
            'minutes': bars_taken * 15
        })
        
    res_df = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print(f"{'START':<20} | {'GAIN %':<8} | {'TIME TAKEN':<15} | {'SPEED (%/h)'}")
    print("-" * 80)
    
    res_df['speed'] = res_df['gain'] / (res_df['minutes']/60)
    
    # Sort by Speed (Most violent first)
    res_df = res_df.sort_values('speed', ascending=False)
    
    for _, r in res_df.iterrows():
        print(f"{r['start_time']} | {r['gain']:<6.1f}% | {r['minutes']:<3.0f} min ({r['bars']} bar) | {r['speed']:.1f} %/h")
        
    print("-" * 80)
    print(f"FOUND {len(res_df)} SPEED DEMONS.")

if __name__ == "__main__":
    run_impulse_scan()
