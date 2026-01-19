"""
XVGUSDT Deep Micro-Audit (ARCH_0 & ARCH_4)
===========================================
Compares successful vs failed signals of ARCH_0 and ARCH_4.
Looking for the 'Precision Tipping Point'.
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
    if (loss == 0).any(): return pd.Series(50, index=prices.index)
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def normalize_sequence(df_seq):
    base_price = df_seq.iloc[0]['open']
    base_vol = df_seq['volume'].mean()
    if base_vol == 0: base_vol = 1
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']:
        normalized[col] = (df_seq[col] / base_price - 1) * 100
    normalized['volume'] = df_seq['volume'] / base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']].values

def calculate_dna_score(current_dna, ideal_dna):
    dist = np.linalg.norm(current_dna - ideal_dna)
    return np.exp(-dist / 50.0) 

def main():
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

    target_archetypes = ['ARCH_0', 'ARCH_4']
    audit_results = {name: [] for name in target_archetypes}

    for idx in range(50, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        for name in target_archetypes:
            dna = archetype_dnas[name]
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > 0.65:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                row = df_1d.loc[idx]
                is_hit = next_date in dg_dates
                audit_results[name].append({
                    'date': row['datetime'].date(),
                    'score': score,
                    'is_hit': is_hit,
                    'rsi': row['rsi'],
                    'vol_ratio': row['vol_ratio']
                })

    for name in target_archetypes:
        print(f"\n" + "="*50)
        print(f"Deep Micro-Audit: {name}")
        print("="*50)
        df = pd.DataFrame(audit_results[name])
        if df.empty: continue
        
        hits = df[df['is_hit']]
        fails = df[~df['is_hit']]
        
        print(f"Hits ({len(hits)}):")
        print(f"  Avg RSI: {hits['rsi'].mean():.1f} | Min Vol: {hits['vol_ratio'].min():.1f}x")
        
        print(f"Fails ({len(fails)}):")
        print(f"  Avg RSI: {fails['rsi'].mean():.1f} | Max Vol: {fails['vol_ratio'].max():.1f}x")
        
        # Identify "Safest Filter"
        if not hits.empty:
            best_vol = hits['vol_ratio'].min()
            potential_p = len(hits[hits['vol_ratio'] >= best_vol]) / (len(hits[hits['vol_ratio'] >= best_vol]) + len(fails[fails['vol_ratio'] >= best_vol]))
            print(f"  Safest Vol Filter (>{best_vol:.1f}x) Precision: {potential_p*100:.1f}%")

if __name__ == "__main__":
    main()
