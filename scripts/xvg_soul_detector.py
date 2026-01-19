"""
XVGUSDT Optimized "Soul" Detector
==================================
Uses learned thresholds specifically for XVGUSDT.
Features: 4H RSI expansion, MACD directional harmony, and EMA9 anchoring.
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

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

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

def xvg_soul_check(row_1d, df_4h, mode):
    """Refined check based on actual XVG Diamond DNA."""
    sig_date = row_1d['datetime']
    target_dt = sig_date + timedelta(days=1)
    
    period_4h = df_4h[df_4h['datetime'] < target_dt].tail(1)
    if period_4h.empty: return False
    b4 = period_4h.iloc[0]
    
    # Mode specific rules derived from debug:
    if mode == 'MOMENTUM':
        # XVG can go up to 95 RSI on 4H and still Diamond
        if b4['rsi'] < 40: return False # Momentum needs some 4H floor
        return True # If daily momentum is there, 4H is likely just following
        
    if mode == 'REVERSAL':
        # Reversals can start from extreme 4H lows (RSI 17)
        return True # Daily reversal signal is the main spark
        
    if mode == 'TREND':
        # Trend needs 4H to be above its own EMA9 to ensure it hasn't broken yet
        if b4['close'] < b4['ema9']: return False
        return True

    return True

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['ema9'] = df_1d['close'].ewm(span=9).mean()
    macd, _, hist = calculate_macd(df_1d['close']), None, None # Reuse local calc
    df_1d['macd_hist'] = calculate_macd(df_1d['close'])
    df_1d['macd_rising'] = df_1d['macd_hist'] > df_1d['macd_hist'].shift(1)

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])
    df_4h['ema9'] = df_4h['close'].ewm(span=9).mean()

    results = {'REVERSAL': [], 'MOMENTUM': [], 'TREND': []}

    for idx in df_1d.index:
        if idx + 1 >= len(df_1d): continue
        sig_date = df_1d.loc[idx, 'datetime'].date()
        next_date = df_1d.loc[idx+1, 'datetime'].date()
        is_hit = next_date in dg_dates
        row = df_1d.loc[idx]

        # REVERSAL: RSI < 40 + MACD Rising
        if row['rsi'] < 40 and row['macd_rising']:
            if xvg_soul_check(row, df_4h, 'REVERSAL'):
                results['REVERSAL'].append(is_hit)

        # MOMENTUM: RSI > 75 + MACD Rising + Above EMA9
        if row['rsi'] > 75 and row['macd_rising'] and row['close'] > row['ema9']:
            if xvg_soul_check(row, df_4h, 'MOMENTUM'):
                results['MOMENTUM'].append(is_hit)

        # TREND: RSI 55-72 + MACD Rising + Above EMA9
        if 55 <= row['rsi'] <= 72 and row['macd_rising'] and row['close'] > row['ema9']:
            if xvg_soul_check(row, df_4h, 'TREND'):
                results['TREND'].append(is_hit)

    print("\n" + "="*80)
    print(f"{'Detector':<15} | {'Signals':<8} | {'Hits':<5} | {'Precision':<10} | {'Recall':<10}")
    print("-" * 80)
    
    for name, hits in results.items():
        count = len(hits)
        correct = sum(hits)
        p = (correct / count * 100) if count > 0 else 0
        r = (correct / len(dg_dates) * 100)
        print(f"{name:<15} | {count:<8} | {correct:<5} | {p:8.1f}% | {r:8.1f}%")

if __name__ == "__main__":
    main()
