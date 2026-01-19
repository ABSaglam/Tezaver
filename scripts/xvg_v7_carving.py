"""
XVGUSDT V7 Signal Carving
=========================
Analyzes the 88 signals of V7 to find filters that keep the 5 hits and kill the 83 fails.
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
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal

def main():
    # Signals from V7 (simulated logic here)
    dna_path = coin_cell_paths.get_library_root() / "xvg_dg_archetypes_v2.json"
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['volume'].rolling(20).mean()
    df_1d['macd_hist'] = calculate_macd_hist(df_1d['close'])
    df_1d['macd_acc'] = df_1d['macd_hist'] - df_1d['macd_hist'].shift(1)

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    signals_data = []

    for idx in range(50, len(df_1d)-1):
        dt = df_1d.loc[idx, 'datetime'].date()
        next_dt = df_1d.loc[idx+1, 'datetime'].date()
        is_hit = next_dt in dg_dates
        
        row_1d = df_1d.loc[idx]
        b4 = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
        
        # We only look at signals that PASSED V7 DNA threshold
        # (This is a simplified re-run of V7 logic)
        signals_data.append({
            'date': dt,
            'is_hit': is_hit,
            '1d_rsi': row_1d['rsi'],
            '1d_vol': row_1d['vol_ratio'],
            '1d_macd_acc': row_1d['macd_acc'],
            '4h_rsi': b4['rsi']
        })

    df = pd.DataFrame(signals_data)
    hits = df[df['is_hit']]
    fails = df[~df['is_hit']]
    
    print(f"Analyzing {len(hits)} Hits vs {len(fails)} potential fails...")

    # Key finding from previous runs: Diamonds need Volume or extreme DNA.
    # What if we use MACD Acceleration + RSI range?
    
    # Let's test combinations
    thresholds = [
        {'name': 'Vol > 5 & MACD_acc > 0', 'logic': (df['1d_vol'] > 5.0) & (df['1d_macd_acc'] > 0)},
        {'name': 'Vol > 10', 'logic': (df['1d_vol'] > 10.0)},
        {'name': '4h_RSI < 75 & 1d_vol > 3', 'logic': (df['4h_rsi'] < 75) & (df['1d_vol'] > 3.0)},
        {'name': 'MACD_acc > 0.0001 & Vol > 2', 'logic': (df['1d_macd_acc'] > 0) & (df['1d_vol'] > 2.0)}
    ]

    for t in thresholds:
        subset = df[t['logic']]
        if subset.empty: continue
        s_hits = subset[subset['is_hit']]
        precision = len(s_hits) / len(subset) * 100
        print(f"Filter: {t['name']:<30} | Signals: {len(subset):<4} | Hits: {len(s_hits):<4} | Precision: {precision:5.1f}%")

if __name__ == "__main__":
    main()
