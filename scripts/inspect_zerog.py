
import pandas as pd
import numpy as np

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

# Coin is 0GUSDT (Zero G)
path = "/Users/alisaglam/TezaverMac/coin_cells/0GUSDT/data/history_15m.parquet"
try:
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    
    # 30 Jan 2026
    start_time = pd.Timestamp("2026-01-30 00:00")
    end_time = pd.Timestamp("2026-01-30 23:59")
    
    subset = df[(df.index >= start_time) & (df.index <= end_time)].copy()
    
    if subset.empty:
        print("No data for 0GUSDT on 30 Jan.")
    else:
        print("--- 0GUSDT (Zero G) 30 JAN DATA ---")
        day_low = subset['low'].min()
        day_high = subset['high'].max()
        rally_pct = ((day_high - day_low) / day_low) * 100
        print(f"Day Low: {day_low} -> Day High: {day_high} (Rally: {rally_pct:.2f}%)")
        
        # Trigger Check: 00:45
        trig_time = pd.Timestamp("2026-01-30 00:45")
        if trig_time in subset.index:
            row = subset.loc[trig_time]
            print(f"\nTrigger Candle (00:45): Open={row['open']}, Close={row['close']}, Vol={row['volume']}")
            
            # Check Peak in next 24h
            future = df[df.index > trig_time].head(96)
            peak = future['high'].max()
            gain = ((peak - row['close']) / row['close']) * 100
            print(f"Peak after trigger: {peak} (+{gain:.2f}%)")

except Exception as e:
    print(f"Error: {e}")
