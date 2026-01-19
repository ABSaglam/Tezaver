"""
XVGUSDT Advanced Feature Mining (Fixed)
========================================
Calculates BB Width, MACD Acceleration, and RSI-EMA for XVG Diamonds vs Failures.
Correctly implements rolling calculations on the full dataframe.
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

def calculate_macd(prices):
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist

def calculate_bb_width(prices, window=20, num_std=2):
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    upper = sma + (std * num_std)
    lower = sma - (std * num_std)
    width = (upper - lower) / sma
    return width

def mine_advanced_features():
    print("="*100)
    print("🔬 XVGUSDT - ADVANCED FEATURE MINING (Bollinger, MACD-acc, RSI-EMA)")
    print("="*100)

    # Load Data
    symbol = 'XVGUSDT'
    path_1d = coin_cell_paths.get_history_file(symbol, '1d')
    df_1d = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    # Indicators (Pre-calculate everything)
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['rsi_ema7'] = df_1d['rsi'].ewm(span=7, adjust=False).mean()
    
    _, _, hist = calculate_macd(df_1d['close'])
    df_1d['macd_hist'] = hist
    df_1d['macd_acc'] = hist - hist.shift(1) # Second derivative (slope)
    
    df_1d['bb_width'] = calculate_bb_width(df_1d['close'])
    df_1d['bb_squeeze'] = df_1d['bb_width'] / df_1d['bb_width'].rolling(50).mean() # Relative width
    
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']

    # Ground Truth
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, tier FROM rallies WHERE symbol = 'XVGUSDT'")
    rallies = cursor.fetchall()
    conn.close()

    rally_map = {pd.to_datetime(t).date(): tier for t, tier in rallies}

    # Extract features for Diamonds
    diamond_stats = []
    other_stats = []

    for idx in range(50, len(df_1d)-1):
        dt = df_1d.loc[idx, 'datetime'].date()
        next_dt = df_1d.loc[idx+1, 'datetime'].date()
        tier = rally_map.get(next_dt, 'NONE')

        row = df_1d.loc[idx]
        stats = {
            'date': dt,
            'rsi_above_ema': row['rsi'] > row['rsi_ema7'],
            'macd_acc': row['macd_acc'],
            'bb_squeeze': row['bb_squeeze'],
            'vol_ratio': row['vol_ratio'],
            'rsi': row['rsi']
        }

        if tier == 'DIAMOND':
            diamond_stats.append(stats)
        else:
            other_stats.append(stats)

    # Analyze
    print(f"\nAnalysis of 16 Diamonds:")
    df_d = pd.DataFrame(diamond_stats)
    
    print(f"  RSI > RSI_EMA7: {df_d['rsi_above_ema'].sum() / len(df_d) * 100:.1f}% of Diamonds")
    print(f"  Avg BB Squeeze: {df_d['bb_squeeze'].mean():.2f} (Max: {df_d['bb_squeeze'].max():.2f})")
    print(f"  MACD Acceleration Positive: {(df_d['macd_acc'] > 0).sum() / len(df_d) * 100:.1f}%")
    print(f"  Avg Vol Ratio: {df_d['vol_ratio'].mean():.1f}x (Min: {df_d['vol_ratio'].min():.1f}x)")

    # Feature Discovery - High Precision candidates
    # Let's try to find a combination that captures many diamonds but very few others.
    
    # Candidate Set 1: BB Squeeze < 1.0 AND RSI > RSI_EMA7 AND MACD_acc > 0
    candidate_1 = df_d[(df_d['bb_squeeze'] <= 1.2) & (df_d['rsi_above_ema']) & (df_d['macd_acc'] > 0)]
    print(f"\nPotential Rule: BB_Squeeze <= 1.2 & RSI > RSI_EMA7 & MACD_acc > 0")
    print(f"  Captured Diamonds: {len(candidate_1)} / {len(df_d)} ({len(candidate_1)/len(df_d)*100:.1f}%)")
    
    df_o = pd.DataFrame(other_stats)
    fp_1 = df_o[(df_o['bb_squeeze'] <= 1.2) & (df_o['rsi_above_ema']) & (df_o['macd_acc'] > 0)]
    print(f"  Global False Positives: {len(fp_1)}")
    
    # Candidate Set 2: Vol Ratio > 3.0 AND BB Squeeze < 1.5
    candidate_2 = df_d[(df_d['vol_ratio'] > 3.0) & (df_d['bb_squeeze'] <= 1.5)]
    print(f"\nPotential Rule: Vol_Ratio > 3.0 & BB_Squeeze <= 1.5")
    print(f"  Captured Diamonds: {len(candidate_2)} / {len(df_d)} ({len(candidate_2)/len(df_d)*100:.1f}%)")
    fp_2 = df_o[(df_o['vol_ratio'] > 3.0) & (df_o['bb_squeeze'] <= 1.5)]
    print(f"  Global False Positives: {len(fp_2)}")

if __name__ == "__main__":
    mine_advanced_features()
