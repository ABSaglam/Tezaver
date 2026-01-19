"""
PEPEUSDT Fine-Grained DNA Extractor (V2)
=========================================
Clusters 22 PEPE Diamonds into 12 specific archetypes for high-precision matching.
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
    base_vol = df_seq['volume'].mean() or 1
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']:
        normalized[col] = (df_seq[col] / base_price - 1) * 100
    normalized['volume'] = df_seq['volume'] / base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']].values.flatten()

def main():
    symbol = 'PEPEUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT raw_data FROM rallies WHERE symbol = ? AND tier = 'DIAMOND'", (symbol,))
    rallies = cursor.fetchall()
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    dna_matrix = []
    for (raw_data,) in rallies:
        raw = json.loads(raw_data)
        start_time = pd.to_datetime(raw['start_time'])
        idx_list = df_1d[df_1d['datetime'] < start_time].index[-2:]
        if len(idx_list) < 2: continue
        dna_matrix.append(normalize_sequence(df_1d.loc[idx_list]))

    if not dna_matrix:
        print("No DNA data.")
        return

    # 12 clusters for high specificity
    n_clusters = min(12, len(dna_matrix))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(dna_matrix)
    
    archetypes = {}
    for i in range(n_clusters):
        cluster_points = [dna_matrix[j] for j, label in enumerate(kmeans.labels_) if label == i]
        if cluster_points:
            archetype_dna = np.mean(cluster_points, axis=0)
            archetypes[f"PEPE_FINE_ARCH_{i}"] = archetype_dna.reshape(2, 5).tolist()

    output_path = "library/pepe_dg_fine_archetypes_v2.json"
    with open(output_path, 'w') as f:
        json.dump(archetypes, f, indent=2)
    
    print(f"\n✅ 12 Fine-Grained PEPE Archetypes saved to: {output_path}")

if __name__ == "__main__":
    main()
