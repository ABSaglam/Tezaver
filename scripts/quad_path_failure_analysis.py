"""
Quadratic Cluster Path Failure Analysis
========================================
Investigates the 2 false positives from VOL_SURGE and MOMENTUM paths.
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

def calculate_macd_hist(prices):
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal

def normalize_sequence(df_seq):
    if len(df_seq) < 2: return None
    base_price = df_seq.iloc[0]['open']
    base_vol = df_seq['volume'].mean() or 1
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']: normalized[col] = (df_seq[col]/base_price-1)*100
    normalized['volume'] = df_seq['volume']/base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']].values

def calculate_dna_score(current_dna, ideal_dna):
    return np.exp(-np.linalg.norm(current_dna - ideal_dna)/50.0)

def main():
    # Failures from previous run
    failures = [
        ('OMUSDT', '2024-06-07', 'VOL_SURGE'),  # score=0.955
        ('RAYUSDT', '2024-03-07', 'MOMENTUM'),  # score=0.869
    ]
    
    hits_momentum = [
        ('SYNUSDT', '2024-08-16'),
        ('SYNUSDT', '2025-07-18'),
        ('OMUSDT', '2023-04-08'),
        ('MDTUSDT', '2024-03-06'),
        ('MDTUSDT', '2025-07-07'),
        ('RAYUSDT', '2024-11-06'),
    ]
    
    print("="*100)
    print("🔍 PATH FAILURE ANALYSIS")
    print("="*100)
    
    for symbol, dt_str, path in failures:
        print(f"\n{path} FAIL: {symbol} @ {dt_str}")
        
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
        df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
        df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
        df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
        df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
        
        sig_dt = pd.to_datetime(dt_str).date()
        row = df_1d[df_1d['datetime'].dt.date == sig_dt].iloc[0]
        idx = row.name
        
        # Previous day stats
        prev_row = df_1d.loc[idx-1]
        prev_ch = prev_row['daily_ch']
        
        print(f"  EMA Dist: {row['ema_dist']:.1f}%")
        print(f"  Daily Ch: {row['daily_ch']:.1f}%")
        print(f"  Vol Ratio: {row['vol_ratio']:.1f}x")
        print(f"  Prev Day Ch: {prev_ch:.1f}%")

if __name__ == "__main__":
    main()
