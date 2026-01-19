"""
Quadratic Cluster Unified Detector
==================================
Tests a single logic across SYN, OM, MDT, RAY.
Rule: DNA Score > 0.98 + Weekly MACD Slope > 0.
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
    base_price = df_seq.iloc[0]['open']
    base_vol = df_seq['volume'].mean() or 1
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']: normalized[col] = (df_seq[col]/base_price-1)*100
    normalized['volume'] = df_seq['volume']/base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']].values

def calculate_dna_score(current_dna, ideal_dna):
    return np.exp(-np.linalg.norm(current_dna - ideal_dna)/50.0)

def main():
    with open("library/quad_cluster_archetypes.json", 'r') as f: archetypes = json.load(f)
    symbols = ['SYNUSDT', 'OMUSDT', 'MDTUSDT', 'RAYUSDT']
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    global_stats = []

    for symbol in symbols:
        print(f"Testing {symbol}...")
        cursor.execute("SELECT raw_data FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
        dg_dates = set([pd.to_datetime(json.loads(r[0])['start_time']).date() for r in cursor.fetchall()])
        
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        
        df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
        df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
        df_1w['w_slope'] = calculate_macd_hist(df_1w['close']).diff()

        coin_archetypes = archetypes[symbol]
        
        for idx in range(25, len(df_1d)-1):
            row_1d = df_1d.loc[idx]
            norm_dna = normalize_sequence(df_1d.iloc[idx-1:idx+1])
            best_score = max([calculate_dna_score(norm_dna, np.array(v)) for v in coin_archetypes])
            
            w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
            
            if best_score > 0.98 and w_row['w_slope'] > 0:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                global_stats.append({'symbol': symbol, 'is_hit': next_date in dg_dates})

    df = pd.DataFrame(global_stats)
    print("\n" + "="*50)
    print("🌍 GLOBAL CLUSTER RESULTS")
    print("="*50)
    if not df.empty:
        print(f"Total Signals: {len(df)}")
        print(f"Precision:    {(df['is_hit'].mean()*100):.1f}%")
        print("\nBreakdown by Coin:")
        print(df.groupby('symbol')['is_hit'].agg(['count', 'mean']))
    else:
        print("No signals found.")

if __name__ == "__main__":
    main()
