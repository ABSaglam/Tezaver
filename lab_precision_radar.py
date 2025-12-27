
import pandas as pd
import numpy as np
from pathlib import Path

def run_precision_radar():
    symbol = "ADAUSDT"
    print(f"🎯 PRECISION RADAR: {symbol}")
    
    path = Path(f"coin_cells/{symbol}/data/history_15m.parquet")
    if not path.exists(): return
    df = pd.read_parquet(path)
    
    # Normalize Time
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.sort_values('open_time').reset_index(drop=True)
    
    # 1. FIND PEAKS (Local Maxima > 30% Gain from recent low)
    # We cheat. We find huge gains first.
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=200) # Look ahead 2 days
    df['future_max'] = df['close'].rolling(window=indexer).max()
    df['gain_pot'] = (df['future_max'] - df['close']) / df['close'] * 100
    
    # Filter candidates (approximate starts)
    candidates = df[df['gain_pot'] > 30.0].index
    
    print(f"Scanning {len(candidates)} potential zones for exact Start/End...")
    
    rallies = []
    processed_indices = set()
    
    for idx in candidates:
        if idx in processed_indices: continue
        
        # This 'idx' is a low point (because gain potential is high).
        # Let's verify it is the TRUE Start (Local Min).
        # We look around small window
        
        start_idx = idx
        # Find the Peak (The target of this gain)
        # Search forward 200 bars for the max price
        future_window = df.loc[idx:idx+200]
        peak_idx = future_window['close'].idxmax()
        peak_price = df.loc[peak_idx, 'close']
        
        # Refine Start: Walk backwards from Peak to find the LOWEST LOW
        # The 'rally' starts from the absolute bottom before the peak.
        # But we stop if we hit a previous peak (drawdown logic).
        # Simple Logic: The Start is the global min in the window [Peak-200 : Peak]
        # Wait, that might go too far back.
        # Let's say Start is the min price between (Peak-100) and Peak.
        
        scan_back_limit = max(0, peak_idx - 100)
        pre_window = df.loc[scan_back_limit:peak_idx]
        true_start_idx = pre_window['low'].idxmin() # Use LOW for wicks
        start_price = df.loc[true_start_idx, 'low'] # Wick bottom
        
        # Calculate Exact Stats
        gain_pct = (peak_price - start_price) / start_price * 100
        duration_bars = peak_idx - true_start_idx
        
        if gain_pct < 30: continue # Maybe strict refinement disqualified it
        
        # Mark processed
        # Mark everything in this rally range as processed to avoid duplicates
        for i in range(true_start_idx, peak_idx + 10):
            processed_indices.add(i)
            
        rallies.append({
            'start_time': df.loc[true_start_idx, 'open_time'],
            'end_time': df.loc[peak_idx, 'open_time'],
            'duration_hours': duration_bars * 15 / 60,
            'bars': duration_bars,
            'gain_pct': gain_pct,
            'start_price': start_price,
            'end_price': peak_price
        })
        
    # Sort and Dedupe
    rallies_df = pd.DataFrame(rallies).sort_values('start_time')
    
    print("\n" + "="*80)
    print(f"{'START':<20} | {'END':<20} | {'DUR (h)':<6} | {'BARS':<5} | {'GAIN %':<8}")
    print("-" * 80)
    
    for _, r in rallies_df.iterrows():
        print(f"{r['start_time']} | {r['end_time']} | {r['duration_hours']:<6.1f} | {r['bars']:<5} | {r['gain_pct']:<6.1f}%")
        
    print("-" * 80)
    print("LOGIC: Start = Lowest Wick, End = Highest Close/High.")

if __name__ == "__main__":
    run_precision_radar()
