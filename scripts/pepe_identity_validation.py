"""
PEPEUSDT Identity Validation
=============================
Checks how many signals the 1.000 DNA match produces for PEPE.
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

def normalize_sequence(df_seq):
    base_price = df_seq.iloc[0]['open']
    base_vol = df_seq['volume'].mean() or 1
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']:
        normalized[col] = (df_seq[col] / base_price - 1) * 100
    normalized['volume'] = df_seq['volume'] / base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']].values

def calculate_dna_score(current_dna, ideal_dna):
    dist = np.linalg.norm(current_dna - ideal_dna)
    return np.exp(-dist / 50.0) 

def main():
    dna_path = "library/pepe_dg_fine_archetypes_v2.json"
    with open(dna_path, 'r') as f:
        fine_dnas = json.load(f)
    
    symbol = 'PEPEUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    signals = []
    for idx in range(25, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        norm_dna = normalize_sequence(df_seq)
        best_score = max([calculate_dna_score(norm_dna, np.array(v)) for v in fine_dnas.values()])
        
        if best_score > 0.999:
            signals.append(df_1d.loc[idx, 'datetime'].date())

    print(f"PEPE Identity Signals Found: {len(signals)}")
    for s in signals:
        print(f"  - {s}")

if __name__ == "__main__":
    main()
