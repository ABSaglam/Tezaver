"""
XVGUSDT Sequence & Resonance Detector
======================================
Focuses on 2-day sequences and ATR/Volume resonance between 1d and 4h.
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

def calculate_macd_hist(prices):
    ema_fast = prices.ewm(span=12).mean()
    ema_slow = prices.ewm(span=26).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9).mean()
    return macd_line - signal_line

def check_resonance(idx, df_1d, df_4h):
    """Checks if Daily and 4H are in 'Resonance'."""
    sig_1d = df_1d.loc[idx]
    
    # 1. ATR Resonance: Daily ATR must be higher than 5-day avg ATR
    atr_ma5 = df_1d['atr'].iloc[max(0, idx-4):idx+1].mean()
    if sig_1d['atr'] < atr_ma5 * 0.8: return False # Must at least be near avg volatility
    
    # 2. Volume Resonance: Look at last 2 4H bars before signal close
    target_dt = sig_1d['datetime'] + timedelta(days=1)
    period_4h = df_4h[df_4h['datetime'] < target_dt].tail(2)
    if len(period_4h) < 2: return False
    
    last_4h = period_4h.iloc[-1]
    prev_4h = period_4h.iloc[-2]
    
    # 4H MACD must be rising internally
    if last_4h['macd_hist'] <= prev_4h['macd_hist']: return False
    
    # 4H RSI must not be extremely fatigued (allow up to 85 instead of 75 for XVG)
    if last_4h['rsi'] > 85: return False
    
    return True

def sequence_detector(idx, df_1d):
    """Looks for the 'Soul' sequence of XVG Diamonds."""
    if idx < 2: return False, "NONE"
    
    day_0 = df_1d.loc[idx]      # Signal Day
    day_1 = df_1d.loc[idx-1]    # Day before Signal
    
    # SEQUENCE TYPE 1: "Quiet Accumulation Breakout"
    # Small volatility on Day -1, followed by a 'warming' Day 0
    if day_1['atr'] < 10 and day_0['atr'] > day_1['atr'] * 1.2:
        if day_0['rsi'] > 50 and day_0['macd_hist'] > day_1['macd_hist']:
            return True, "QUIET_BREAK"

    # SEQUENCE TYPE 2: "Volatile Continuation"
    # Strong Day -1, with Day 0 maintaining the heat
    if day_1['rsi'] > 65 and day_0['rsi'] > day_1['rsi'] and day_0['vol_ratio'] > 1.2:
        return True, "VOLS_CONT"
        
    # SEQUENCE TYPE 3: "Extreme Reversal"
    # Very low RSI but Day 0 starting to point up
    if day_1['rsi'] < 35 and day_0['rsi'] > day_1['rsi'] and day_0['macd_hist'] > day_1['macd_hist']:
        return True, "EXT_REV"

    return False, "NONE"

def main():
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['macd_hist'] = calculate_macd_hist(df_1d['close'])
    df_1d['atr'] = (df_1d['high'] - df_1d['low']) / df_1d['close'] * 100
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['volume'].rolling(20).mean()

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])
    df_4h['macd_hist'] = calculate_macd_hist(df_4h['close'])

    hits = []
    signals = []
    
    for idx in df_1d.index:
        if idx + 1 >= len(df_1d): continue
        pass_seq, seq_name = sequence_detector(idx, df_1d)
        
        if pass_seq:
            if check_resonance(idx, df_1d, df_4h):
                sig_date = df_1d.loc[idx, 'datetime'].date()
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                signals.append(sig_date)
                if next_date in dg_dates:
                    hits.append(next_date)

    print("\n" + "="*80)
    print("🎯 XVGUSDT SEQUENCE & RESONANCE DETECTOR RESULTS")
    print("="*80)
    print(f"Total Signals: {len(signals)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(signals)*100 if signals else 0):.1f}%")
    print(f"Recall:       {(len(hits)/len(dg_dates)*100 if dg_dates else 0):.1f}%")

if __name__ == "__main__":
    main()
