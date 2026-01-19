"""
XVGUSDT Diamond DNA Extractor
==============================
Extracts and averages the 3-day OHLCV sequence for all 16 Diamonds to create a 'Search Template'.
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
    """Normalizes price and volume data for the sequence."""
    base_price = df_seq.iloc[0]['open']
    base_vol = df_seq['volume'].mean()
    
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']:
        normalized[col] = (df_seq[col] / base_price - 1) * 100
    
    normalized['volume'] = df_seq['volume'] / base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']]

def main():
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier = 'DIAMOND'")
    diamonds = cursor.fetchall()
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    sequences = []
    
    for (raw_data,) in diamonds:
        raw = json.loads(raw_data)
        start_time = pd.to_datetime(raw['start_time'])
        
        # Get Day -2, Day -1
        idx_list = df_1d[df_1d['datetime'] < start_time].index[-2:]
        if len(idx_list) < 2: continue
        
        df_seq = df_1d.loc[idx_list]
        sequences.append(normalize_sequence(df_seq).values)

    if not sequences:
        print("No sequences found.")
        return

    # Average DNA
    avg_dna = np.mean(sequences, axis=0)
    
    print("\n" + "="*80)
    print("💎 XVGUSDT IDEAL DIAMOND DNA (Normalized 2-day precursor)")
    print("="*80)
    print("Columns: [Open%, High%, Low%, Close%, VolumeRatio]")
    print(f"Day -2:\n{avg_dna[0]}")
    print(f"Day -1:\n{avg_dna[1]}")
    
    # Save DNA to JSON
    output_path = coin_cell_paths.get_library_root() / "xvg_diamond_dna.json"
    with open(output_path, 'w') as f:
        json.dump(avg_dna.tolist(), f)
    
    print(f"\n✅ Ideal DNA saved to: {output_path}")

if __name__ == "__main__":
    main()
