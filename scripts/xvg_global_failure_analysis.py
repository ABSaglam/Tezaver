"""
XVGUSDT Full Detector Autopsy
==============================
Analyzes why signals FAILED across all three detectors.
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
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def detector_a_reversal(df_1d, df_1w, idx):
    sig = df_1d.loc[idx]
    if sig['rsi'] >= 50: return False
    if sig['macd_hist'] >= 0 or not sig['macd_rising']: return False
    
    sig_date = sig['datetime']
    week_rows = df_1w[df_1w['datetime'] <= sig_date]
    if len(week_rows) == 0: return False
    last_week = week_rows.iloc[-1]
    if last_week['rsi'] < 55 or last_week['close'] <= last_week['ema9']: return False
    return True

def detector_c_trend(df_1d, idx):
    sig = df_1d.loc[idx]
    if sig['rsi'] < 55 or sig['rsi'] > 72: return False
    if sig['macd_hist'] <= 0 or not sig['macd_rising']: return False
    if sig['close'] <= sig['ema9']: return False
    return True

def analyze_all_failures():
    print("="*100)
    print("🔬 XVGUSDT - GLOBAL FAILURE ANALYSIS")
    print("="*100)
    
    # Get ground truth
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data, tier FROM rallies WHERE symbol = 'XVGUSDT'")
    all_rallies = cursor.fetchall()
    conn.close()
    
    rally_map = {}
    dg_dates = set()
    for _, raw_data, tier in all_rallies:
        raw = json.loads(raw_data)
        start_date = pd.to_datetime(raw['start_time']).date()
        rally_map[start_date] = {'tier': tier, 'gain': raw['gain']}
        if tier in ['DIAMOND', 'GOLD']: dg_dates.add(start_date)
    
    # Load data
    path_1d = coin_cell_paths.get_history_file('XVGUSDT', '1d')
    df_1d = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['ema9'] = df_1d['close'].ewm(span=9).mean()
    
    macd, _, hist = calculate_macd(df_1d['close'])
    df_1d['macd_hist'] = hist
    df_1d['macd_rising'] = hist > hist.shift(1)
    
    df_1w = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1w')).sort_values('timestamp')
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['rsi'] = calculate_rsi(df_1w['close'])
    df_1w['ema9'] = df_1w['close'].ewm(span=9).mean()
    
    detectors = {
        'A_REVERSAL': detector_a_reversal,
        'C_TREND': detector_c_trend
    }
    
    for name, detector in detectors.items():
        print(f"\n🚫 {name} FAILURES")
        print("-" * 50)
        failures = []
        for idx in df_1d.index:
            if idx + 1 >= len(df_1d): continue
            
            # Pass 1w for A
            res = detector(df_1d, df_1w, idx) if name == 'A_REVERSAL' else detector(df_1d, idx)
            
            if res:
                sig_date = df_1d.loc[idx, 'datetime'].date()
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                if next_date not in dg_dates:
                    sig = df_1d.loc[idx]
                    next_day = df_1d.loc[idx+1]
                    next_tier = rally_map.get(next_date, {}).get('tier', 'NONE')
                    failures.append({'date': sig_date, 'tier': next_tier, 'rsi': sig['rsi'], 'close_change': (next_day['close']/sig['close']-1)*100})
        
        # Report top failures
        df_fail = pd.DataFrame(failures)
        if not df_fail.empty:
            print(f"Total Failures: {len(df_fail)}")
            print(f"Tier Distribution:\n{df_fail['tier'].value_counts()}")
            print(f"Avg RSI of failures: {df_fail['rsi'].mean():.1f}")
            print(f"Sample failures (last 5):")
            for _, row in df_fail.tail(5).iterrows():
                print(f"  {row['date']}: Result={row['tier']} (Next Day: {row['close_change']:.1f}%) | RSI: {row['rsi']:.1f}")
        else:
            print("No failures found (unlikely).")

if __name__ == "__main__":
    analyze_all_failures()
