"""
XVGUSDT Triple Detector Backtest
=================================
Tests 3 separate detection strategies:
- Detector A: Reversal Hunter (cold start)
- Detector B: Momentum Surfer (overheated)
- Detector C: Trend Follower (balanced)
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

def detector_a_reversal(df_1d, df_4h, df_1w, idx):
    """Detector A: Reversal Hunter (Cold Start)"""
    sig = df_1d.loc[idx]
    
    # Daily: Cold/weak
    if sig['rsi'] >= 50:
        return False, "RSI too high"
    
    # Daily: MACD turning
    if sig['macd_hist'] >= 0 or not sig['macd_rising']:
        return False, "MACD not turning"
    
    # Weekly: Must be strong
    sig_date = sig['datetime']
    week_rows = df_1w[df_1w['datetime'] <= sig_date]
    if len(week_rows) == 0:
        return False, "No weekly data"
    
    last_week = week_rows.iloc[-1]
    if last_week['rsi'] < 55:
        return False, "Weekly RSI too low"
    if last_week['close'] <= last_week['ema9']:
        return False, "Weekly below EMA9"
    
    return True, "REVERSAL"

def detector_b_momentum(df_1d, idx):
    """Detector B: Momentum Surfer (Overheated)"""
    sig = df_1d.loc[idx]
    
    # RSI very high
    if sig['rsi'] < 75:
        return False, "RSI not hot enough"
    
    # MACD green and rising
    if sig['macd_hist'] <= 0:
        return False, "MACD not positive"
    if not sig['macd_rising']:
        return False, "MACD not rising"
    
    # Big candle body
    body = abs(sig['close'] - sig['open']) / sig['open'] * 100
    if body < 15:
        return False, "Body too small"
    
    # Above EMA9
    if sig['close'] <= sig['ema9']:
        return False, "Not above EMA9"
    
    return True, "MOMENTUM"

def detector_c_trend(df_1d, idx):
    """Detector C: Trend Follower (Balanced)"""
    sig = df_1d.loc[idx]
    
    # RSI comfortable zone
    if sig['rsi'] < 55 or sig['rsi'] > 72:
        return False, "RSI out of zone"
    
    # MACD green and rising
    if sig['macd_hist'] <= 0:
        return False, "MACD not positive"
    if not sig['macd_rising']:
        return False, "MACD not rising"
    
    # Above EMA9
    if sig['close'] <= sig['ema9']:
        return False, "Not above EMA9"
    
    return True, "TREND"

def backtest_detectors():
    print("="*100)
    print("🧪 XVGUSDT - TRIPLE DETECTOR BACKTEST (3 Years)")
    print("="*100)
    
    # Load ground truth DG
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_time, raw_data FROM rallies 
        WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')
        ORDER BY event_time
    """)
    dg_rallies = cursor.fetchall()
    conn.close()
    
    dg_dates = set()
    for event_time, raw_data in dg_rallies:
        raw = json.loads(raw_data)
        start_date = pd.to_datetime(raw['start_time']).date()
        dg_dates.add(start_date)
    
    print(f"Ground Truth: {len(dg_dates)} DG rally dates\n")
    
    # Load data
    print("Loading data...")
    path_1d = coin_cell_paths.get_history_file('XVGUSDT', '1d')
    path_4h = coin_cell_paths.get_history_file('XVGUSDT', '4h')
    path_1w = coin_cell_paths.get_history_file('XVGUSDT', '1w')
    
    df_1d = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['ema9'] = df_1d['close'].ewm(span=9).mean()
    
    macd, macd_signal, hist = calculate_macd(df_1d['close'])
    df_1d['macd_hist'] = hist
    df_1d['macd_rising'] = hist > hist.shift(1)
    
    df_4h = None
    if path_4h.exists():
        df_4h = pd.read_parquet(path_4h).sort_values('timestamp')
        df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    
    df_1w = None
    if path_1w.exists():
        df_1w = pd.read_parquet(path_1w).sort_values('timestamp')
        df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
        df_1w['rsi'] = calculate_rsi(df_1w['close'])
        df_1w['ema9'] = df_1w['close'].ewm(span=9).mean()
    
    print("Data loaded.\n")
    
    # Test each detector
    results = {
        'A_REVERSAL': {'signals': [], 'caught_dg': []},
        'B_MOMENTUM': {'signals': [], 'caught_dg': []},
        'C_TREND': {'signals': [], 'caught_dg': []}
    }
    
    print("Running backtest...")
    for idx in df_1d.index:
        if idx + 1 >= len(df_1d):
            continue
        
        sig_date = df_1d.loc[idx, 'datetime'].date()
        next_date = df_1d.loc[idx+1, 'datetime'].date()
        
        # Check if next day has DG
        is_dg = next_date in dg_dates
        
        # Test Detector A
        pass_a, reason_a = detector_a_reversal(df_1d, df_4h, df_1w, idx)
        if pass_a:
            results['A_REVERSAL']['signals'].append(sig_date)
            if is_dg:
                results['A_REVERSAL']['caught_dg'].append(next_date)
        
        # Test Detector B
        pass_b, reason_b = detector_b_momentum(df_1d, idx)
        if pass_b:
            results['B_MOMENTUM']['signals'].append(sig_date)
            if is_dg:
                results['B_MOMENTUM']['caught_dg'].append(next_date)
        
        # Test Detector C
        pass_c, reason_c = detector_c_trend(df_1d, idx)
        if pass_c:
            results['C_TREND']['signals'].append(sig_date)
            if is_dg:
                results['C_TREND']['caught_dg'].append(next_date)
    
    # Report
    print("="*100)
    print("📊 BACKTEST RESULTS")
    print("="*100)
    
    total_dg = len(dg_dates)
    
    for detector, data in results.items():
        signals = len(data['signals'])
        caught = len(data['caught_dg'])
        catch_rate = (caught / total_dg * 100) if total_dg > 0 else 0
        precision = (caught / signals * 100) if signals > 0 else 0
        
        print(f"\n{detector}:")
        print(f"  Total Signals: {signals}")
        print(f"  DG Caught: {caught}/{total_dg} ({catch_rate:.0f}%)")
        print(f"  Precision: {precision:.0f}% ({caught} correct out of {signals} signals)")
        print(f"  False Positives: {signals - caught}")
    
    # Combined
    print(f"\n{'='*100}")
    print(f"COMBINED (all 3 detectors):")
    all_signals = set()
    all_caught = set()
    
    for detector, data in results.items():
        all_signals.update(data['signals'])
        all_caught.update(data['caught_dg'])
    
    combined_signals = len(all_signals)
    combined_caught = len(all_caught)
    combined_catch_rate = (combined_caught / total_dg * 100) if total_dg > 0 else 0
    combined_precision = (combined_caught / combined_signals * 100) if combined_signals > 0 else 0
    
    print(f"  Total Signals: {combined_signals}")
    print(f"  DG Caught: {combined_caught}/{total_dg} ({combined_catch_rate:.0f}%)")
    print(f"  Precision: {combined_precision:.0f}%")
    
    return results

if __name__ == "__main__":
    results = backtest_detectors()
