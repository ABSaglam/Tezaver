"""
Quadratic Cluster Statistical Mining (Train Zone)
=================================================
Mines features for ALL training signals with DNA > 0.85.
Goal: Find the 100% precision threshold for the cluster.
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
    stats = []

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
            if row['datetime'] >= test_start: continue # Strictly keep test zone out
            
            norm_dna = normalize_sequence(df_1d.iloc[idx-1:idx+1])
            if norm_dna is None: continue
            score = max([calculate_dna_score(norm_dna, np.array(v)) for v in coin_archetypes])
            
            w_row = df_1w[df_1w['datetime'] <= row['datetime']].iloc[-1]
            
            if score > 0.85 and w_row['w_slope'] > 0:
                is_hit = (df_1d.loc[idx+1, 'datetime'].date() in dg_dates)
                stats.append({
                    'is_hit': is_hit,
                    'ema_dist': row['ema_dist'],
                    'score': score
                })

    df = pd.DataFrame(stats)
    print("\n" + "="*80)
    print("📋 TRAIN ZONE STATISTICAL RECAP")
    print("="*80)
    if not df.empty:
        print(df.groupby('is_hit').mean())
        
        # Check EMA Dist threshold
        hits = df[df['is_hit']]
        print(f"\nHit EMA Dist Range: {hits['ema_dist'].min():.1f}% to {hits['ema_dist'].max():.1f}%")
        
        potential_rule = hits['ema_dist'].min()
        precision = df[df['ema_dist'] >= potential_rule]['is_hit'].mean()
        print(f"Precision with EMA Dist >= {potential_rule:.1f}%: {precision*100:.1f}%")
    else:
        print("No training signals found.")

if __name__ == "__main__":
    main()
