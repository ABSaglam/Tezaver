"""
Quad Cluster Rally Coverage Analysis
=====================================
Analyzes why we only catch 11 out of ~220 DG rallies.
Goal: Find more safe detection paths.
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
    with open("library/quad_cluster_archetypes_full.json", 'r') as f: archetypes = json.load(f)
    symbols = ['SYNUSDT', 'OMUSDT', 'MDTUSDT', 'RAYUSDT']
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    total_dg = 0
    caught = 0
    missed_stats = []

    for symbol in symbols:
        cursor.execute("SELECT raw_data FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
        rallies = cursor.fetchall()
        total_dg += len(rallies)
        
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
        df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
        df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
        
        df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
        df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
        df_1w['w_slope'] = calculate_macd_hist(df_1w['close']).diff()

        coin_archs = archetypes[symbol]
        
        for (raw_data,) in rallies:
            raw = json.loads(raw_data)
            start_time = pd.to_datetime(raw['start_time'])
            signal_date = (start_time - timedelta(days=1)).date()
            
            row = df_1d[df_1d['datetime'].dt.date == signal_date]
            if row.empty: continue
            row = row.iloc[0]
            idx = row.name
            if idx < 26: continue
            
            prev_row = df_1d.loc[idx-1]
            norm_dna = normalize_sequence(df_1d.iloc[idx-1:idx+1])
            if norm_dna is None: continue
            score = max([calculate_dna_score(norm_dna, np.array(v)) for v in coin_archs])
            
            w_row = df_1w[df_1w['datetime'] <= row['datetime']].iloc[-1]
            
            # Check if this rally was caught by V5 rules
            is_ghost = score >= 1.0 and row['ema_dist'] >= 10.0 and row['daily_ch'] >= 5.0 and w_row['w_slope'] > 0
            is_momentum = score >= 0.85 and row['daily_ch'] >= 15.0 and row['ema_dist'] >= 20.0 and prev_row['daily_ch'] >= 5.0 and w_row['w_slope'] > 0
            
            if is_ghost or is_momentum:
                caught += 1
            else:
                missed_stats.append({
                    'symbol': symbol,
                    'score': score,
                    'ema_dist': row['ema_dist'],
                    'daily_ch': row['daily_ch'],
                    'prev_ch': prev_row['daily_ch'],
                    'w_slope': w_row['w_slope'],
                    'gain': raw['gain']
                })

    df = pd.DataFrame(missed_stats)
    print("="*80)
    print(f"📊 QUAD CLUSTER RALLY COVERAGE ANALYSIS")
    print("="*80)
    print(f"\nTotal DG Rallies: {total_dg}")
    print(f"Caught: {caught}")
    print(f"Missed: {len(df)}")
    print(f"Coverage: {(caught/total_dg*100):.1f}%")
    
    print("\n--- MISSED RALLY STATISTICS ---")
    print(df.describe().loc[['mean', 'min', 'max', '50%']])
    
    print("\n--- WHY MISSED? ---")
    low_score = len(df[df['score'] < 0.85])
    low_ema = len(df[(df['score'] >= 0.85) & (df['ema_dist'] < 10)])
    low_daily = len(df[(df['score'] >= 0.85) & (df['daily_ch'] < 5)])
    bear_week = len(df[df['w_slope'] <= 0])
    
    print(f"  Low DNA Score (<0.85): {low_score}")
    print(f"  Low EMA Distance (<10%): {low_ema}")
    print(f"  Low Daily Change (<5%): {low_daily}")
    print(f"  Bearish Weekly: {bear_week}")

if __name__ == "__main__":
    main()
