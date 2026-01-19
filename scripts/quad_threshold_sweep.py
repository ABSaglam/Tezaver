"""
Quadratic Cluster Threshold Sweeper
====================================
Sweeps EMA_DIST and DNA_SCORE to find 100% precision islands.
Train Zone Only.
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
    with open("library/quad_cluster_archetypes_isolated.json", 'r') as f: archetypes = json.load(f)
    symbols = ['SYNUSDT', 'OMUSDT', 'MDTUSDT', 'RAYUSDT']
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    test_start = datetime(2025, 10, 1)
    data = []

    for symbol in symbols:
        cursor.execute("SELECT raw_data FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
        dg_dates = set([pd.to_datetime(json.loads(r[0])['start_time']).date() for r in cursor.fetchall()])
        
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
        df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
        
        df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
        df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
        df_1w['w_slope'] = calculate_macd_hist(df_1w['close']).diff()

        coin_archetypes = archetypes[symbol]
        
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['datetime'] >= test_start: continue
            
            norm_dna = normalize_sequence(df_1d.iloc[idx-1:idx+1])
            if norm_dna is None: continue
            score = max([calculate_dna_score(norm_dna, np.array(v)) for v in coin_archetypes])
            
            w_row = df_1w[df_1w['datetime'] <= row['datetime']].iloc[-1]
            if w_row['w_slope'] > 0:
                is_hit = (df_1d.loc[idx+1, 'datetime'].date() in dg_dates)
                data.append({'is_hit': is_hit, 'ema': row['ema_dist'], 'score': score})

    df = pd.DataFrame(data)
    
    print("="*60)
    print("🌊 THRESHOLD SWEEP (TRAIN ZONE)")
    print("="*60)
    print(f"{'EMA >=':<10} | {'DNA >=':<10} | {'SIGNALS':<10} | {'PRECISION'}")
    print("-" * 60)

    for e_limit in [5, 10, 15, 20, 25]:
        for d_limit in [0.90, 0.95, 0.98]:
            subset = df[(df['ema'] >= e_limit) & (df['score'] >= d_limit)]
            if not subset.empty:
                prec = subset['is_hit'].mean() * 100
                print(f"{e_limit:>8.1f}% | {d_limit:>8.2f} | {len(subset):>8} | {prec:>8.1f}%")

if __name__ == "__main__":
    main()
