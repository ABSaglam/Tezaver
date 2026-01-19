"""
XVGUSDT Stealth Gold Signature Extraction
==========================================
Analyzes the specific conditions of the low-volume GOLD rallies.
Matches them against thousands of failed signals to find a unique differentiator.
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

def calculate_bb_width(prices, window=20):
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    return (std * 4) / sma

def main():
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_rallies = [(pd.to_datetime(json.loads(r[1])['start_time']).date(), r[0]) for r in cursor.fetchall()]
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    
    # Advanced Differentiators
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['bb_width'] = calculate_bb_width(df_1d['close'])
    df_1d['bb_width_ma10'] = df_1d['bb_width'].rolling(10).mean()
    df_1d['bb_squeeze'] = df_1d['bb_width'] / df_1d['bb_width_ma10']
    
    ema9 = df_1d['close'].ewm(span=9, adjust=False).mean()
    ema21 = df_1d['close'].ewm(span=21, adjust=False).mean()
    df_1d['trend_harmony'] = ema9 > ema21
    
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['volume'].rolling(20).mean()

    # Targets: Stealth golds (Vol < 4)
    stealth_targets = ['2023-05-20', '2025-11-01', '2025-10-09']
    
    print("="*100)
    print("🕵️ STEALTH GOLD SIGNATURE ANALYSIS")
    print("="*100)
    
    target_data = []
    for dt_str in stealth_targets:
        dt = pd.to_datetime(dt_str).date()
        # The signal day is dt - 1 day
        sig_day = dt - timedelta(days=1)
        row = df_1d[df_1d['datetime'].dt.date == sig_day]
        if row.empty: continue
        row = row.iloc[0]
        
        target_data.append({
            'date': sig_day,
            'rsi': row['rsi'],
            'bb_squeeze': row['bb_squeeze'],
            'trend': row['trend_harmony'],
            'vol': row['vol_ratio']
        })
        print(f"Target {dt_str}: RSI={row['rsi']:.1f}, Squeeze={row['bb_squeeze']:.2f}, Trend={row['trend_harmony']}, Vol={row['vol_ratio']:.1f}x")

    # Now find ANY other day in 3 years that matches this signature (Stealth Filter)
    # Let's define the filter: BB_Squeeze < 0.8 (Extreme Squeeze) AND Trend == True AND RSI between 45-70
    
    matches = df_1d[(df_1d['bb_squeeze'] < 0.8) & (df_1d['trend_harmony'] == True) & (df_1d['rsi'] > 45) & (df_1d['rsi'] < 70)]
    
    print(f"\nPotential Stealth Filter Results (BB_Squeeze < 0.8 & Trend & RSI 45-70):")
    for _, match in matches.iterrows():
        next_date = (match['datetime'] + timedelta(days=1)).date()
        is_hit = any(d[0] == next_date for d in dg_rallies)
        hit_label = "✅ HIT" if is_hit else "❌ FAIL"
        print(f"  {match['datetime'].date()} -> {next_date}: {hit_label} | Vol: {match['vol_ratio']:.1f}x")

if __name__ == "__main__":
    main()
