import pandas as pd
import numpy as np
import os

symbol = "ZROUSDT"
target_time = pd.Timestamp("2025-12-01 20:45:00")

def debug_ribbon():
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    
    # EMAs
    periods = [20, 25, 30, 35, 40, 45, 50, 55]
    ema_vals = {}
    for p in periods:
        df[f'ema_{p}'] = df['close'].ewm(span=p, adjust=False).mean()
    
    if target_time not in df.index:
        print(f"Target time {target_time} not in index.")
        return
        
    row = df.loc[target_time]
    print(f"--- {symbol} @ {target_time} ---")
    print(f"Close: {row['close']}")
    
    ordered = True
    vals = []
    for p in periods:
        val = row[f'ema_{p}']
        vals.append(val)
        print(f"EMA {p}: {val:.6f}")
        
    # Check alignment: 20 > 25 > 30...
    for i in range(len(vals)-1):
        if not (vals[i] > vals[i+1]):
            print(f"ALignment Error at index {i}: EMA {periods[i]} ({vals[i]:.6f}) is NOT > EMA {periods[i+1]} ({vals[i+1]:.6f})")
            ordered = False
            
    if ordered:
        print("Ribbon is perfectly ALIGNED.")
        # Slope
        prev_idx = df.index.get_loc(target_time) - 1
        ema20_prev = df.iloc[prev_idx]['ema_20']
        slope = ((row['ema_20'] / ema20_prev) - 1) * 100
        print(f"Slope: %{slope:.2f}")
    else:
        print("Ribbon is NOT aligned.")

if __name__ == "__main__":
    debug_ribbon()
