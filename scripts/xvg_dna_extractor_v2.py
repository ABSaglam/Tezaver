"""
XVGUSDT Advanced DNA Extractor (46 DG Rallies)
================================================
Extracts and clusters DNA from all 46 Diamond/Gold rallies into 6 Archetypes.
Uses 3-day sequences for deeper pattern matching.
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3
from sklearn.cluster import KMeans

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

def normalize_sequence(df_seq):
    base_price = df_seq.iloc[0]['open']
    base_vol = df_seq['volume'].mean()
    if base_vol == 0: base_vol = 1
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']:
        normalized[col] = (df_seq[col] / base_price - 1) * 100
    normalized['volume'] = df_seq['volume'] / base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']].values.flatten()

def main():
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    rallies = cursor.fetchall()
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    dna_matrix = []
    
    for (raw_data,) in rallies:
        raw = json.loads(raw_data)
        start_time = pd.to_datetime(raw['start_time'])
        # Get 3 days of context (Day -2, Day -1, Day -0 is the rally start)
        # We look at Day -2 and Day -1 for the PRE-rally signature
        idx_list = df_1d[df_1d['datetime'] < start_time].index[-2:]
        if len(idx_list) < 2: continue
        dna_matrix.append(normalize_sequence(df_1d.loc[idx_list]))

    if not dna_matrix:
        print("No DNA data found.")
        return

    # Cluster into 6 types to capture more subtle signatures
    # Use fewer clusters if we don't have enough data points, but 46 is enough for 6.
    n_clusters = 6
    if len(dna_matrix) < n_clusters: n_clusters = len(dna_matrix)
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(dna_matrix)
    
    archetypes = {}
    for i in range(n_clusters):
        archetype_dna = np.mean([dna_matrix[j] for j, label in enumerate(kmeans.labels_) if label == i], axis=0)
        archetypes[f"ARCH_{i}"] = archetype_dna.reshape(2, 5).tolist()

    output_path = coin_cell_paths.get_library_root() / "xvg_dg_archetypes_v2.json"
    with open(output_path, 'w') as f:
        json.dump(archetypes, f, indent=2)
    
    print(f"\n✅ 6 Archetype DNAs (from 46 DG) saved to: {output_path}")
    print(f"Clusters: {pd.Series(kmeans.labels_).value_counts().to_dict()}")

if __name__ == "__main__":
    main()
