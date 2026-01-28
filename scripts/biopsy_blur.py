
import pandas as pd
import numpy as np
import os
import math

def geometric_biopsy():
    symbol = "BLURUSDT"
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    
    if not os.path.exists(path):
        print("❌ File not found")
        return

    df = pd.read_parquet(path)
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
    df.sort_index(inplace=True)
    
    # RSI & Ribbon EMA 20 Calculation
    delta = df['close'].diff()
    alpha = 1 / 11
    gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
    rsi = 100 - (100 / (1 + (gain / loss)))
    ema20 = rsi.ewm(span=20, adjust=False).mean()
    
    # Target Timestamps (UTC)
    targets = [
        "2026-01-14 21:00:00",
        "2026-01-14 21:15:00",
        "2026-01-14 21:30:00"
    ]
    
    print(f"📐 GEOMETRIC BIOPSY: {symbol} EMA 20 (RSI Ribbon Upper)")
    print("-" * 60)
    
    results = []
    for t in targets:
        ts = pd.Timestamp(t)
        if df.index.tz is not None:
            ts = ts.tz_localize('UTC').tz_convert(df.index.tz)
        
        if ts in ema20.index:
            val = ema20.loc[ts]
            results.append((t, val))
            print(f"Time: {t} | EMA 20 Value: {val:.4f}")
        else:
            print(f"❌ {t} not found in index.")

    if len(results) == 3:
        v1 = results[0][1]
        v2 = results[1][1]
        v3 = results[2][1]
        
        # Slope 1: 21:00 -> 21:15
        diff1 = v2 - v1
        angle1 = math.degrees(math.atan(diff1))
        
        # Slope 2: 21:15 -> 21:30
        diff2 = v3 - v2
        angle2 = math.degrees(math.atan(diff2))
        
        print("-" * 60)
        print(f"📈 SEGMENT 1 (21:00 -> 21:15): Diff={diff1:+.4f} | Angle={angle1:+.2f}°")
        print(f"📈 SEGMENT 2 (21:15 -> 21:30): Diff={diff2:+.4f} | Angle={angle2:+.2f}°")
        print("-" * 60)
        
        # User requested horizontal perspective (normalize to first point)
        print("Relative Horizontal Progression (Base 0 at 21:00):")
        print(f"21:00: 0.0000")
        print(f"21:15: {v2-v1:+.4f}")
        print(f"21:30: {v3-v1:+.4f}")

if __name__ == "__main__":
    geometric_biopsy()
