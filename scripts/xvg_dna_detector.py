"""
XVGUSDT DNA Score Detector
===========================
Calculates the 'DNA Similarity Score' for every day against the ideal Diamond DNA.
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
    base_vol = df_seq['volume'].mean()
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']:
        normalized[col] = (df_seq[col] / base_price - 1) * 100
    normalized['volume'] = df_seq['volume'] / base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']].values

def calculate_dna_score(current_dna, ideal_dna):
    """Calculates similarity (Euclidean distance based) score 0-1.0."""
    dist = np.linalg.norm(current_dna - ideal_dna)
    # Scale: A distance of 100 means very different, 0 means identical.
    score = np.exp(-dist / 50.0) 
    return score

def main():
    # Load Ideal DNA
    dna_path = coin_cell_paths.get_library_root() / "xvg_diamond_dna.json"
    with open(dna_path, 'r') as f:
        ideal_dna = np.array(json.load(f))

    # Load Ground Truth
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    # Load Price Data
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    signals = []
    
    # Threshold for DNA similarity
    THRESHOLD = 0.65 

    for idx in range(2, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1] # Last 2 days
        current_dna = normalize_sequence(df_seq)
        
        score = calculate_dna_score(current_dna, ideal_dna)
        
        if score > THRESHOLD:
            sig_date = df_1d.loc[idx, 'datetime'].date()
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            is_hit = next_date in dg_dates
            signals.append({'date': sig_date, 'score': score, 'is_hit': is_hit})

    if not signals:
        print("No signals found at this threshold.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"🧬 XVGUSDT DNA SCORE DETECTOR (Threshold: {THRESHOLD})")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")
    print(f"Recall:       {(len(hits)/len(dg_dates)*100 if dg_dates else 0):.1f}%")

    # Show top signals
    print("\nTop Signal Samples:")
    for _, row in sig_df.sort_values('score', ascending=False).head(10).iterrows():
        hit_icon = "✅" if row['is_hit'] else "❌"
        print(f"  {row['date']}: Score {row['score']:.3f} {hit_icon}")

if __name__ == "__main__":
    main()
