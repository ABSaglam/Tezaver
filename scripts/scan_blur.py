
import pandas as pd
import numpy as np
import sys
import os
import math

def scan_indicators():
    symbol = "BLURUSDT"
    target_date = "2026-01-14"
    target_time = "21:30"
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    
    if not os.path.exists(path):
        print("❌ File not found")
        return

    df = pd.read_parquet(path)
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    
    # Try different RSI periods
    for rsi_p in [11, 14]:
        print(f"\n--- TESTING RSI PERIOD: {rsi_p} ---")
        delta = df['close'].diff()
        alpha = 1 / rsi_p
        gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
        rsi = 100 - (100 / (1 + (gain / loss)))
        
        target_ts = pd.Timestamp(f"{target_date} {target_time}")
        if df.index.tz is not None:
            target_ts = target_ts.tz_localize(df.index.tz)
            
        idx = rsi.index.get_loc(target_ts)
        
        print(f"RSI Value at {target_time}: {rsi.iloc[idx]:.2f}")
        print(f"RSI Value at 21:15: {rsi.iloc[idx-1]:.2f}")
        
        # Test Ribbon spans from 10 to 100
        print("\nSlope Analysis (EMA Spans):")
        for span in [11, 20, 30, 40, 50, 60, 80, 100]:
            ema = rsi.ewm(span=span, adjust=False).mean()
            v_curr = ema.iloc[idx]
            v_prev = ema.iloc[idx-1]
            diff = v_curr - v_prev
            angle = math.degrees(math.atan(diff))
            print(f"EMA {span:3}: Value={v_curr:6.2f}, Diff={diff:+6.2f}, Angle={angle:+6.2f}°")

if __name__ == "__main__":
    scan_indicators()
