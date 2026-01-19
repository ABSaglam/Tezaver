"""
XVGUSDT DNA Clusterer
======================
Groups the 16 Diamonds into 3 Archetypes and saves their DNAs.
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
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']:
        normalized[col] = (df_seq[col] / base_price - 1) * 100
    normalized['volume'] = df_seq['volume'] / base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']].values.flatten()

def main():
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier = 'DIAMOND'")
    diamonds = cursor.fetchall()
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    dna_matrix = []
    
    for (raw_data,) in diamonds:
        raw = json.loads(raw_data)
        start_time = pd.to_datetime(raw['start_time'])
        idx_list = df_1d[df_1d['datetime'] < start_time].index[-2:]
        if len(idx_list) < 2: continue
        dna_matrix.append(normalize_sequence(df_1d.loc[idx_list]))

    # Cluster into 3 types
    kmeans = KMeans(n_clusters=3, random_state=42).fit(dna_matrix)
    
    archetypes = {}
    for i in range(3):
        archetype_dna = np.mean([dna_matrix[j] for j, label in enumerate(kmeans.labels_) if label == i], axis=0)
        archetypes[f"TYPE_{chr(65+i)}"] = archetype_dna.reshape(2, 5).tolist()

    output_path = coin_cell_paths.get_library_root() / "xvg_archetype_dnas.json"
    with open(output_path, 'w') as f:
        json.dump(archetypes, f, indent=2)
    
    print(f"\n✅ 3 Archetype DNAs saved to: {output_path}")
    print(f"Clusters: {pd.Series(kmeans.labels_).value_counts().to_dict()}")

if __name__ == "__main__":
    main()
