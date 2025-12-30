import pandas as pd
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from tezaver.ui.chart_area import load_history_data
from tezaver.core.config import to_turkey_time


def calc_gain_at(df, idx, bars):
    p_start = df.iloc[idx]['open']
    idx_end = min(len(df)-1, idx + bars)
    p_end = df.iloc[idx_end]['high']
    gain = (p_end - p_start) / p_start
    print(f"GAIN @ idx {idx} (+{bars} bars): {gain*100:.2f}% (Price: {p_start} -> {p_end})")

def main():
    symbol = "ADAUSDT"
    tf = "15m"
    event_str = "2025-10-10 21:15:00"
    bars = 47
    
    print(f"--- DEBUGGING {symbol} {tf} ---")
    df = load_history_data(symbol, tf)
    if df is None:
        print("Data load failed")
        return

    # Normalize DF
    if 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
        # Sort
        df = df.sort_values('open_time').reset_index(drop=True)
    
    print(f"Data range: {df['open_time'].min()} to {df['open_time'].max()}")
    
    print(f"Sample dates: {df['open_time'].head(3).tolist()}")
    
    # Target Event Time (From DB String)
    event_str = "2025-10-10 21:15:00"
    ts_naive = pd.to_datetime(event_str)
    
    # Probe 1: Exact Naive Match (if data naive)
    print(f"--- Probe 1: Naive {ts_naive} ---")
    matches = df[df['open_time'].dt.tz_localize(None) == ts_naive]
    if not matches.empty:
        idx = matches.index[0]
        print(f"MATCH (Naive) at idx {idx}")
        calc_gain_at(df, idx, bars)
    else:
        print("No Naive match")

    # Probe 2: Input as TRT -> Convert to UTC 
    # If 21:15 is TRT, then UTC is 18:15
    ts_trt = ts_naive - pd.Timedelta(hours=3)
    print(f"--- Probe 2: Assumed TRT Input -> UTC {ts_trt} ---")
    matches = df[df['open_time'].dt.tz_localize(None) == ts_trt]
    if not matches.empty:
        idx = matches.index[0]
        print(f"MATCH (UTC-Shifted) at idx {idx}")
        calc_gain_at(df, idx, bars)
    else:
        print("No UTC-Shifted match")
        
    print("--- SCANNING FOR 46% GAIN on 2025-10-10 ---")
    # Filter for Oct 10
    start_dt = pd.to_datetime("2025-10-10 00:00:00").tz_localize('UTC')
    end_dt = pd.to_datetime("2025-10-11 00:00:00").tz_localize('UTC')
    
    subset = df[(df['open_time'] >= start_dt) & (df['open_time'] < end_dt)]
    
    found = False
    for i in range(len(subset)):
        idx = subset.index[i]
        
        # Check +47 bars
        if idx + bars < len(df):
            p_start = df.iloc[idx]['open']
            p_end = df.iloc[idx+bars]['high']
            gain = (p_end - p_start) / p_start
            
            if gain > 0.40: # Look for >40%
                print(f"FOUND! Time: {df.iloc[idx]['open_time']} | Gain: {gain*100:.2f}% | Price: {p_start} -> {p_end}")
                found = True
                
    if not found:
        print("No >40% gain found on Oct 10 with 47 bar duration.")

if __name__ == "__main__":
    main()

def calc_gain_at(df, idx, bars):
    p_start = df.iloc[idx]['open']
    idx_end = min(len(df)-1, idx + bars)
    p_end = df.iloc[idx_end]['high']
    gain = (p_end - p_start) / p_start
    print(f"GAIN @ idx {idx} (+{bars} bars): {gain*100:.2f}% (Price: {p_start} -> {p_end})")
