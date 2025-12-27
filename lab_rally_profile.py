
import pandas as pd
import numpy as np
from pathlib import Path

def run_profile():
    symbol = "ADAUSDT"
    target_start = "2025-03-02 15:15:00"
    
    print(f"📉 RALLY PROFILER: {symbol} @ {target_start}")
    
    path = Path(f"coin_cells/{symbol}/data/history_15m.parquet")
    if not path.exists(): return
    df = pd.read_parquet(path)
    
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.sort_values('open_time').reset_index(drop=True)
    
    # Locate Start
    target_ts = pd.to_datetime(target_start)
    if df['open_time'].dt.tz is not None and target_ts.tz is None:
        target_ts = target_ts.tz_localize('UTC')
        
    mask = df['open_time'] == target_ts
    if not mask.any():
        print("Start time not found.")
        return
        
    start_idx = df.index[mask][0]
    start_price = df.loc[start_idx, 'open'] # Assuming entry at Open of the signal candle? Or Close?
    # Usually we enter at Close of trigger or Open of next.
    # Let's assume Entry = Close of 15:15 bar (Trigger confirmed)
    entry_price = df.loc[start_idx, 'close']
    
    print(f"ENTRY: {target_ts} | Price: {entry_price}")
    
    # Analyze next 40 bars (10 hours)
    print("\nBAR-BY-BAR PROGRESSION:")
    print(f"{'TIME':<20} | {'BAR':<3} | {'PRICE':<8} | {'GAIN %':<8} | {'STATUS'}")
    print("-" * 65)
    
    max_gain = 0
    peak_time = None
    
    for i in range(1, 41):
        idx = start_idx + i
        if idx >= len(df): break
        
        row = df.loc[idx]
        current_gain = (row['close'] - entry_price) / entry_price * 100
        high_gain = (row['high'] - entry_price) / entry_price * 100
        
        if high_gain > max_gain:
            max_gain = high_gain
            peak_time = row['open_time']
            
        # Check for Local Peaks/Stalls
        status = ""
        if high_gain == max_gain: status = "🆕 PEAK"
        if high_gain > 30 and high_gain < max_gain * 0.9: status = "⚠️ FADING"
        
        print(f"{row['open_time']} | +{i:<2} | {row['close']:<8.4f} | {current_gain:<6.1f}% (H:{high_gain:.1f}%) | {status}")
        
    print("-" * 65)
    print(f"ABSOLUTE PEAK: {max_gain:.2f}% at {peak_time}")
    
    # Efficiency Check
    # Find when we reached 80% of the peak
    threshold_80 = max_gain * 0.80
    for i in range(1, 41):
        idx = start_idx + i
        row = df.loc[idx]
        h_gain = (row['high'] - entry_price) / entry_price * 100
        if h_gain >= threshold_80:
            print(f"⚡ 80% OF MOVE CAPTURED BY: {row['open_time']} (Bar +{i})")
            break

if __name__ == "__main__":
    run_profile()
