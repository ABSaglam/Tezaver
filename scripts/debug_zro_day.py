import pandas as pd
import numpy as np
import os

def debug_zro_full_day():
    symbol = "ZROUSDT"
    df = pd.read_parquet(f'coin_cells/{symbol}/data/history_15m.parquet')
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df.sort_index()

    # Calculate indicators
    periods = [20, 25, 30, 35, 40, 45, 50, 55]
    for p in periods:
        df[f'ema_{p}'] = df['close'].ewm(span=p, adjust=False).mean()
    
    # Target day
    target_day = pd.Timestamp("2025-12-01").normalize()
    day_data = df[df.index.normalize() == target_day].copy()
    
    if day_data.empty:
        print("No data for Dec 1st")
        return

    print(f"--- ZROUSDT Analysis for {target_day.date()} ---")
    print(f"{'Time':<10} | {'EMA20_F':<10} | {'EMA55_F':<10} | {'EMA20_T':<10} | {'EMA55_T':<10}")
    print("-" * 60)
    
    for idx, row in day_data.iterrows():
        # adjust=False (Default)
        ema20_f = df.loc[:idx, 'close'].ewm(span=20, adjust=False).mean().iloc[-1]
        ema55_f = df.loc[:idx, 'close'].ewm(span=55, adjust=False).mean().iloc[-1]
        # adjust=True
        ema20_t = df.loc[:idx, 'close'].ewm(span=20, adjust=True).mean().iloc[-1]
        ema55_t = df.loc[:idx, 'close'].ewm(span=55, adjust=True).mean().iloc[-1]
        
        print(f"{idx.strftime('%H:%M'):<10} | {ema20_f:<10.4f} | {ema55_f:<10.4f} | {ema20_t:<10.4f} | {ema55_t:<10.4f}")

if __name__ == "__main__":
    debug_zro_full_day()
