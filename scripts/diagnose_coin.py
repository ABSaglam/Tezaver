#!/usr/bin/env python3
import sys
import pandas as pd
import numpy as np
from tezaver.core import coin_cell_paths

SYMBOL = "DASHUSDT"

path = coin_cell_paths.get_history_file(SYMBOL, '1d')
if not path.exists():
    print(f"❌ No data found for {SYMBOL}")
    sys.exit()

df = pd.read_parquet(path)
if 'datetime' in df.columns:
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
elif 'timestamp' in df.columns:
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('datetime')

# No need to resample

# Indicators
df['atr_val'] = (df['high'] - df['low']).rolling(14).mean()
df['atr_pct'] = (df['atr_val'] / df['close']) * 100

delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss.replace(0, 0.001)
df['rsi'] = 100 - (100 / (1 + rs))

# Last 30 days to catch the pump
print(f"🔍 DIAGNOSTIC REPORT: {SYMBOL}")
print(f"Latest Date in File: {df.index.max()}")
print("-" * 50)
print(f"{'DATE':<12} {'CLOSE':<10} {'RSI':<6} {'ATR%':<6} {'STATUS'}")
print("-" * 50)

last_rows = df.tail(30)
for date, row in last_rows.iterrows():
    rsi = row['rsi']
    atr = row['atr_pct']
    
    status = "❌ NO"
    if atr > 15 and 55 < rsi < 70: status = "✅ TREND"
    elif 12 < atr <= 15 and 60 < rsi < 75: status = "🥷 NINJA"
    
    # Hints
    fail_reason = []
    if atr <= 12: fail_reason.append("Low Volatility")
    if rsi <= 55: fail_reason.append("RSI too Cold")
    if rsi >= 75: fail_reason.append("RSI too Hot")
    
    if status == "❌ NO" and fail_reason:
        status += f" ({', '.join(fail_reason)})"
        
    print(f"{date.strftime('%Y-%m-%d'):<12} {row['close']:<10.2f} {rsi:<6.1f} {atr:<6.1f} {status}")
print("-" * 50)
print("CRITERIA:")
print("  TREND: ATR > 15% AND RSI 55-70")
print("  NINJA: ATR 12-15% AND RSI 60-75")
