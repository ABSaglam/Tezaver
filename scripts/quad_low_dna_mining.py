"""
Quad Cluster Low-Score Rally Mining
====================================
Explores if low-DNA rallies share other characteristics.
Goal: Find alternative detection paths.
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
    
    # Find rallies with DNA < 0.85 but BULLish weekly
    bullish_low_dna = []

    for symbol in symbols:
        cursor.execute("SELECT raw_data FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
        rallies = cursor.fetchall()
        
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
        
        for (raw_data,) in rallies:
            raw = json.loads(raw_data)
            start_time = pd.to_datetime(raw['start_time'])
            signal_date = (start_time - timedelta(days=1)).date()
            
            row = df_1d[df_1d['datetime'].dt.date == signal_date]
            if row.empty: continue
            row = row.iloc[0]
            idx = row.name
            if idx < 26: continue
            
            norm_dna = normalize_sequence(df_1d.iloc[idx-1:idx+1])
            if norm_dna is None: continue
            score = max([calculate_dna_score(norm_dna, np.array(v)) for v in coin_archs])
            
            w_row = df_1w[df_1w['datetime'] <= row['datetime']].iloc[-1]
            
            # Low DNA but bullish weekly
            if score < 0.85 and w_row['w_slope'] > 0:
                bullish_low_dna.append({
                    'symbol': symbol,
                    'score': score,
                    'ema_dist': row['ema_dist'],
                    'daily_ch': row['daily_ch'],
                    'vol_ratio': row['vol_ratio'],
                    'gain': raw['gain']
                })

    df = pd.DataFrame(bullish_low_dna)
    print("="*80)
    print(f"📊 LOW-DNA BUT BULLISH RALLIES: {len(df)}")
    print("="*80)
    print(df.describe().loc[['mean', 'min', 'max', '50%']])
    
    print("\n--- POTENTIAL FILTERS ---")
    # Check if volume surge can help
    high_vol = df[df['vol_ratio'] >= 2.0]
    print(f"Volume Ratio >= 2x: {len(high_vol)} rallies")
    
    # Check if positive daily change helps
    pos_daily = df[df['daily_ch'] >= 5.0]
    print(f"Daily Change >= 5%: {len(pos_daily)} rallies")
    
    # Combined filter
    combined = df[(df['vol_ratio'] >= 2.0) & (df['daily_ch'] >= 5.0)]
    print(f"Vol >= 2x AND Daily >= 5%: {len(combined)} rallies")
    
    # Strong combined
    strong = df[(df['vol_ratio'] >= 3.0) & (df['daily_ch'] >= 10.0)]
    print(f"Vol >= 3x AND Daily >= 10%: {len(strong)} rallies")

if __name__ == "__main__":
    main()
