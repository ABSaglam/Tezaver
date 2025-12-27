
import pandas as pd
import numpy as np
from pathlib import Path

def run_precision_12h():
    symbol = "ADAUSDT"
    print(f"🎯 PRECISION RADAR (12H LIMIT): {symbol}")
    
    path = Path(f"coin_cells/{symbol}/data/history_15m.parquet")
    if not path.exists(): return
    df = pd.read_parquet(path)
    
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.sort_values('open_time').reset_index(drop=True)
    
    # 1. Broad Scan: >20% Gain within 12 Hours (48 bars)
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=48) 
    df['future_max'] = df['close'].rolling(window=indexer).max()
    df['gain_pot'] = (df['future_max'] - df['close']) / df['close'] * 100
    
    candidates = df[df['gain_pot'] > 20.0].index
    
    rallies = []
    processed_indices = set()
    
    for idx in candidates:
        if idx in processed_indices: continue
        
        # 2. Precision Refinement (Valley to Peak)
        # Find peak within next 48 bars
        future_window = df.loc[idx:idx+48]
        peak_idx = future_window['close'].idxmax()
        peak_price = df.loc[peak_idx, 'close']
        
        # Find True Start (Lowest Low before Peak)
        # Search back up to 48 bars or until previous peak
        scan_back = max(0, peak_idx - 48)
        pre_window = df.loc[scan_back:peak_idx]
        start_idx = pre_window['low'].idxmin()
        start_time = df.loc[start_idx, 'open_time']
        start_price = df.loc[start_idx, 'low']
        
        # Verify Gain matches criteria (End Price - Start Price)
        true_gain = (peak_price - start_price) / start_price * 100
        if true_gain < 20.0: continue
        
        # Mark processed
        for i in range(start_idx, peak_idx + 5):
            processed_indices.add(i)
            
        duration_bars = peak_idx - start_idx
        duration_hours = duration_bars * 15 / 60
        
        rallies.append({
            'start': start_time,
            'end': df.loc[peak_idx, 'open_time'],
            'duration_h': duration_hours,
            'gain': true_gain,
            'speed': true_gain / duration_hours if duration_hours > 0 else 0
        })
        
    rallies_df = pd.DataFrame(rallies).sort_values('start')
    
    print("\n" + "="*85)
    print(f"{'START':<20} | {'END':<20} | {'DUR (h)':<8} | {'GAIN %':<8} | {'SPEED (%/h)'}")
    print("-" * 85)
    
    for _, r in rallies_df.iterrows():
        print(f"{r['start']} | {r['end']} | {r['duration_h']:<6.1f} h | {r['gain']:<6.1f}%  | {r['speed']:.1f} %/h")
        
    print("-" * 85)
    print(f"FOUND {len(rallies_df)} RALLIES (Correct Start/End).")
    
    # Analyze Top 3 Speeds
    print("\n🥇 TOP 3 FASTEST MOVERS:")
    top3 = rallies_df.sort_values('speed', ascending=False).head(3)
    for _, r in top3.iterrows():
         print(f"   {r['start']} -> +{r['gain']:.1f}% in {r['duration_h']:.1f}h")

if __name__ == "__main__":
    run_precision_12h()
