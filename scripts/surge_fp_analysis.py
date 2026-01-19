"""
SURGE Path False Positive Analysis
===================================
Investigates the 13 false positives from SURGE path.
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
    
    hits = []
    fails = []

    for symbol in symbols:
        cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
        all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
        
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
        df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
        df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
        df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
        df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
        
        df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
        df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
        df_1w['w_slope'] = calculate_macd_hist(df_1w['close']).diff()

        coin_archs = archetypes[symbol]
        
        for idx in range(26, len(df_1d)-1):
            row = df_1d.loc[idx]
            prev_row = df_1d.loc[idx-1]
            norm_dna = normalize_sequence(df_1d.iloc[idx-1:idx+1])
            if norm_dna is None: continue
            score = max([calculate_dna_score(norm_dna, np.array(v)) for v in coin_archs])
            
            w_row = df_1w[df_1w['datetime'] <= row['datetime']].iloc[-1]
            
            # SURGE path only
            if score >= 0.60 and row['vol_ratio'] >= 3.0 and row['daily_ch'] >= 10.0 and w_row['w_slope'] > 0:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                
                entry = {
                    'symbol': symbol,
                    'date': row['datetime'].date(),
                    'score': score,
                    'ema_dist': row['ema_dist'],
                    'daily_ch': row['daily_ch'],
                    'vol_ratio': row['vol_ratio'],
                    'prev_ch': prev_row['daily_ch']
                }
                if is_hit: hits.append(entry)
                else: fails.append(entry)

    h_df = pd.DataFrame(hits)
    f_df = pd.DataFrame(fails)
    
    print("="*80)
    print(f"📊 SURGE PATH ANALYSIS: {len(h_df)} Hits, {len(f_df)} Fails")
    print("="*80)
    
    print("\nHITS Statistics:")
    print(h_df[['score', 'ema_dist', 'daily_ch', 'vol_ratio', 'prev_ch']].describe().loc[['mean', 'min', 'max']])
    
    print("\nFAILS Statistics:")
    print(f_df[['score', 'ema_dist', 'daily_ch', 'vol_ratio', 'prev_ch']].describe().loc[['mean', 'min', 'max']])
    
    # Find separator
    print("\n--- POTENTIAL SEPARATORS ---")
    h_min_vol = h_df['vol_ratio'].min()
    h_min_daily = h_df['daily_ch'].min()
    h_min_ema = h_df['ema_dist'].min()
    
    print(f"Hits min Vol: {h_min_vol:.1f}x | Daily: {h_min_daily:.1f}% | EMA: {h_min_ema:.1f}%")
    
    # Test higher thresholds
    for vol_t in [4.0, 5.0, 6.0]:
        for daily_t in [15.0, 20.0]:
            pass_h = len(h_df[(h_df['vol_ratio'] >= vol_t) & (h_df['daily_ch'] >= daily_t)])
            pass_f = len(f_df[(f_df['vol_ratio'] >= vol_t) & (f_df['daily_ch'] >= daily_t)])
            if pass_h > 0:
                prec = pass_h / (pass_h + pass_f) * 100 if (pass_h + pass_f) > 0 else 0
                print(f"Vol>={vol_t:.1f}x, Daily>={daily_t:.1f}%: {pass_h} hits, {pass_f} fails -> {prec:.0f}%")

if __name__ == "__main__":
    main()
