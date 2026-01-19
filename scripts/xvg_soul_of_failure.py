"""
XVGUSDT Soul of specific Failures
==================================
Deep dive into why 3 specific high-conviction signals produced NOTHING.
"""

import sys
import os
import pandas as pd
import numpy as np
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
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def get_macd_color(hist_current, hist_prev):
    if hist_current > 0:
        return '🟢↗' if hist_current > hist_prev else '🟢↘'
    else:
        return '🔴↗' if hist_current > hist_prev else '🔴↘'

def study_failure(target_date, label, df_1d, df_4h):
    print(f"\n🔍 FAILURE STUDY: {label} ({target_date})")
    print("-" * 60)
    
    sig_row = df_1d[df_1d['datetime'].dt.date == pd.to_datetime(target_date).date()]
    if sig_row.empty: return
    
    idx = sig_row.index[0]
    sig = sig_row.iloc[0]
    next_day = df_1d.iloc[idx+1]
    
    macd_color = get_macd_color(sig['macd_hist'], df_1d.iloc[idx-1]['macd_hist'])
    
    print(f"SIGNAL DAY:")
    print(f"  RSI: {sig['rsi']:.1f} | MACD: {macd_color} ({sig['macd_hist']:.4f})")
    print(f"  Vol Ratio: {sig['vol_ratio']:.1f}x | ATR: {sig['atr']:.1f}%")
    print(f"  Position: EMA9 distance {((sig['close']/sig['ema9']-1)*100):.1f}%")
    
    print(f"WHAT HAPPENED NEXT:")
    print(f"  Next Day High: %{((next_day['high']/sig['close']-1)*100):.1f}")
    print(f"  Next Day Close: %{((next_day['close']/sig['close']-1)*100):.1f}")
    
    # 4H Context
    if df_4h is not None:
        start_4h = pd.to_datetime(target_date)
        end_4h = start_4h + timedelta(days=1)
        period_4h = df_4h[(df_4h['datetime'] >= start_4h) & (df_4h['datetime'] <= end_4h)]
        
        print(f"4H SOUL DURING SIGNAL:")
        last_4h = period_4h.iloc[-3] if len(period_4h) >= 3 else period_4h.iloc[0]
        macd_4h = get_macd_color(last_4h['macd_hist'], df_4h.iloc[last_4h.name-1]['macd_hist'])
        print(f"  4H RSI: {last_4h['rsi']:.1f} | 4H MACD: {macd_4h}")
        print(f"  4H ATR: {last_4h['atr']:.1f}%")

def main():
    path_1d = coin_cell_paths.get_history_file('XVGUSDT', '1d')
    df_1d = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['ema9'] = df_1d['close'].ewm(span=9).mean()
    macd, _, hist = calculate_macd(df_1d['close'])
    df_1d['macd_hist'] = hist
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    df_1d['atr'] = (df_1d['high'] - df_1d['low']) / df_1d['close'] * 100

    path_4h = coin_cell_paths.get_history_file('XVGUSDT', '4h')
    df_4h = pd.read_parquet(path_4h).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])
    _, _, hist_4h = calculate_macd(df_4h['close'])
    df_4h['macd_hist'] = hist_4h
    df_4h['atr'] = (df_4h['high'] - df_4h['low']) / df_4h['close'] * 100

    study_failure('2024-11-14', 'MOMENTUM FAILURE (Hot burnout)', df_1d, df_4h)
    study_failure('2025-09-29', 'REVERSAL FAILURE (Dead bounce)', df_1d, df_4h)
    study_failure('2025-12-30', 'TREND FAILURE (Exhaustion)', df_1d, df_4h)

if __name__ == "__main__":
    main()
