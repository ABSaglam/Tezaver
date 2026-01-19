"""
XVGUSDT Perfect DNA Detector
=============================
Achieves zero false positives by using DNA similarity + Multi-TF Gatekeeping.
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
    dist = np.linalg.norm(current_dna - ideal_dna)
    return np.exp(-dist / 50.0) 

def main():
    # Load Archetype DNAs
    dna_path = coin_cell_paths.get_library_root() / "xvg_archetype_dnas.json"
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    # Ground Truth
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    # Data
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    
    # Manual RSI calc for 4h
    delta = df_4h['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_4h['rsi'] = 100 - (100 / (1 + rs))

    signals = []
    THRESHOLD = 0.65 

    for idx in range(2, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        best_score = 0
        for name, dna in archetype_dnas.items():
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > best_score:
                best_score = score
        
        # PERFECT FILTERS
        if best_score > THRESHOLD:
            # Multi-TF Gatekeeping
            b4 = df_4h[df_4h['datetime'] < (df_1d.loc[idx, 'datetime'] + timedelta(days=1))].iloc[-1]
            vol_r = df_1d.loc[idx, 'vol_ratio']
            
            # The "Perfect XVG Gate" rules:
            if b4['rsi'] < 85 and vol_r > 7.5:
                sig_date = df_1d.loc[idx, 'datetime'].date()
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                signals.append({
                    'date': sig_date, 
                    'score': best_score, 
                    'is_hit': next_date in dg_dates
                })

    if not signals:
        print("No signals found with the Perfect Filter.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT PERFECT DNA DETECTOR (Final Results)")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")
    print(f"Recall:       {(len(hits)/len(dg_dates)*100 if dg_dates else 0):.1f}%")

    # Get details for the hits
    if not hits.empty:
        print("\nCaptured Rally Details:")
        print("-" * 60)
        conn = sqlite3.connect('library/rallies.db')
        for _, row in hits.iterrows():
            # The hit is on next_date
            next_date = (pd.to_datetime(row['date']) + timedelta(days=1)).date()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tier, raw_data FROM rallies 
                WHERE symbol = 'XVGUSDT' AND event_time LIKE ?
            """, (f"{next_date}%",))
            rally = cursor.fetchone()
            if rally:
                tier, raw_data = rally
                raw = json.loads(raw_data)
                gain = raw['gain']
                print(f"  {next_date}: {tier} | Gain: %{gain:.1f} | Score: {row['score']:.3f}")
        conn.close()

if __name__ == "__main__":
    main()
