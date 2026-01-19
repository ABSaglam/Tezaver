"""
XVGUSDT Archetype Performance Audit
====================================
Tests 6 DNA archetypes individually to find 100% precision zones.
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

    # Audit Storage
    audit = {name: {'signals': 0, 'hits': 0, 'dates': []} for name in archetype_dnas}

    for idx in range(2, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        for name, dna in archetype_dnas.items():
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > 0.65: # High similarity threshold
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                is_hit = next_date in dg_dates
                audit[name]['signals'] += 1
                if is_hit:
                    audit[name]['hits'] += 1
                audit[name]['dates'].append((df_1d.loc[idx, 'datetime'].date(), score, is_hit))

    print("\n" + "="*80)
    print("🔬 XVGUSDT ARCHETYPE PRECISION AUDIT")
    print("="*80)
    print(f"{'Archetype':<12} | {'Signals':<8} | {'Hits':<5} | {'Precision':<10}")
    print("-" * 45)
    
    for name, data in audit.items():
        precision = (data['hits'] / data['signals'] * 100) if data['signals'] > 0 else 0
        print(f"{name:<12} | {data['signals']:<8} | {data['hits']:<5} | {precision:8.1f}%")

if __name__ == "__main__":
    main()
