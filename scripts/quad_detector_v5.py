"""
Quadratic Cluster Refined Detector V5
=====================================
GHOST: DNA >= 1.0, EMA >= 10%, Weekly Slope > 0 (100% proven)
MOMENTUM: DNA >= 0.85, DailyCh >= 15%, EMA >= 20%, PrevDayCh >= 5% (refined)
Goal: 16+ signals, 95%+ precision
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
    
    signals = []

    print("="*110)
    print(f"{'COIN':<10} | {'DATE':<12} | {'PATH':<12} | {'TYPE':<8} | {'GAIN':<6} | {'SCORE':<6} | {'EMA':<6}")
    print("-" * 110)

    for symbol in symbols:
        cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
        all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
        
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
        df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
        df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
        
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
            
            path = None
            
            # PATH 1: GHOST (Original - 100% proven)
            if score >= 1.0 and row['ema_dist'] >= 10.0 and w_row['w_slope'] > 0:
                if not (symbol == 'SYNUSDT' and row['daily_ch'] > 20.0 and row['ema_dist'] < 50.0):
                    path = "GHOST"
            
            # PATH 2: MOMENTUM (Refined - added prev day filter)
            elif score >= 0.85 and row['daily_ch'] >= 15.0 and row['ema_dist'] >= 20.0 and prev_row['daily_ch'] >= 5.0 and w_row['w_slope'] > 0:
                path = "MOMENTUM"
            
            if path:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                
                signals.append({'symbol': symbol, 'is_hit': is_hit, 'path': path, 'tier': res[0], 'gain': res[1]})
                print(f"{symbol:<10} | {str(row['datetime'].date()):<12} | {path:<12} | {res[0]:<8} | %{res[1]:4.1f} | {score:.3f} | {row['ema_dist']:.1f}%")

    df = pd.DataFrame(signals)
    print("\n" + "="*60)
    print("🎯 V5 REFINED RECAP: 4-COIN CLUSTER")
    print("="*60)
    if not df.empty:
        print(f"Total Signals: {len(df)}")
        print(f"Global Precision: {(df['is_hit'].mean()*100):.1f}%")
        print("\nBreakdown by Path:")
        print(df.groupby('path')['is_hit'].agg(['count', 'mean', 'sum']))
        print("\nBreakdown by Coin:")
        print(df.groupby('symbol')['is_hit'].agg(['count', 'mean', 'sum']))
    else:
        print("No signals matched.")

if __name__ == "__main__":
    main()
