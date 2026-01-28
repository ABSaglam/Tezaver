
import pandas as pd
import numpy as np
import os
import math

def match_user_settings():
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
    
    # 1. RSI(11)
    delta = df['close'].diff()
    alpha = 1 / 11
    gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
    rsi = 100 - (100 / (1 + (gain / loss)))
    
    # 2. RSI-based MA (EMA 11) - TradingView Girdisi
    rsi_ema = rsi.ewm(span=11, adjust=False).mean()
    
    # 3. EMA Ribbon (Source: rsi_ema)
    # User's MA-1 is 20
    ribbon_20 = rsi_ema.ewm(span=20, adjust=False).mean()
    
    # Target Timestamps (normalized to match data)
    targets = ["2026-01-14 21:00:00", "2026-01-14 21:15:00", "2026-01-14 21:30:00"]
    
    print(f"📐 REVERSE ENGINEERING: Matching TradingView Settings")
    print(f"Source Hierarchy: Price -> RSI(11) -> EMA(11) -> EMA(20)")
    print("-" * 60)
    
    for t in targets:
        ts = pd.Timestamp(t)
        # Check for non-tz vs tz
        if df.index.tz is None:
            # Data likely has no tz
            pass
        else:
            ts = ts.tz_localize('UTC').tz_convert(df.index.tz)

        if ts in ribbon_20.index:
            val = ribbon_20.loc[ts]
            print(f"Time: {t} | Script Value: {val:.2f}")
        else:
            # Fallback to nearest if needed
            print(f"❌ {t} not found.")

    print("-" * 60)
    print("User Values: 21:00 -> 53.57, 21:15 -> 53.24, 21:30 -> 53.14")

if __name__ == "__main__":
    match_user_settings()
