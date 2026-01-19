"""
XVGUSDT 4H Diamond State Debugger
==================================
Extracts exact 4H indicator states for the 6 hours preceding each Diamond.
"""

import sys
import os
import pandas as pd
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    return macd_line - signal_line

def main():
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier = 'DIAMOND'")
    diamonds = cursor.fetchall()
    conn.close()

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])
    df_4h['macd_hist'] = calculate_macd(df_4h['close'])
    df_4h['vol_ratio'] = df_4h['volume'] / df_4h['volume'].rolling(20).mean()

    print(f"{'Date':<12} | {'4H RSI':<8} | {'4H MACD Hist':<12} | {'4H Vol Ratio':<12}")
    print("-" * 50)

    for event_time, raw_data in diamonds:
        raw = json.loads(raw_data)
        start_time = pd.to_datetime(raw['start_time'])
        
        # Get the 4H bar exactly before the rally start
        pre_bars = df_4h[df_4h['datetime'] < start_time].tail(1)
        if not pre_bars.empty:
            b = pre_bars.iloc[0]
            print(f"{event_time[:10]:<12} | {b['rsi']:8.1f} | {b['macd_hist']:12.6f} | {b['vol_ratio']:12.2f}")

if __name__ == "__main__":
    main()
