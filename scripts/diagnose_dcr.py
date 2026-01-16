#!/usr/bin/env python3
import pandas as pd
from tezaver.core import coin_cell_paths

def check_dcr():
    path = coin_cell_paths.get_history_file("DCRUSDT", '1d')
    if not path.exists():
        print("DCRUSDT data not found.")
        return

    df = pd.read_parquet(path)
    
    # Calculate Indicators
    df['atr_val'] = (df['high'] - df['low']).rolling(14).mean()
    df['atr_pct'] = (df['atr_val'] / df['close']) * 100
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, 0.001)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    print("📊 DCRUSDT Last 10 Days:")
    print("-" * 50)
    print(f"{'Date':<12} {'RSI':<6} {'ATR%':<6} {'Status'}")
    print("-" * 50)
    
    for _, row in df.tail(10).iterrows():
        status = ""
        # Trend Criteria: ATR > 15, 55 < RSI < 70
        if row['atr_pct'] > 15 and 55 < row['rsi'] < 70:
            status = "🔥 TREND"
        # Ninja Criteria: ATR 12-15, 60 < RSI < 75
        elif 12 < row['atr_pct'] <= 15 and 60 < row['rsi'] < 75:
            status = "🥷 NINJA"
            
        print(f"{row['datetime'].date()}   {row['rsi']:.1f}   {row['atr_pct']:.1f}   {status}")

if __name__ == "__main__":
    check_dcr()
