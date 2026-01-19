"""
PEPEUSDT Baseline Detector V1
==============================
Logic: DNA Score > 0.65 (against 5 Diamond archetypes).
Filters: Daily Vol Ratio > 2.0, 4H RSI < 85.
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
    if (loss == 0).any(): 
        res = pd.Series(50, index=prices.index)
        for i in range(period, len(prices)):
            l = loss.iloc[i]
            if l > 0: res.iloc[i] = 100 - (100 / (1 + gain.iloc[i] / l))
        return res
    rs = gain / loss
    return 100 - (100 / (1 + rs))

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
    dna_path = "library/pepe_dg_archetypes_v1.json"
    if not os.path.exists(dna_path):
        print("DNA archetypes missing.")
        return
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    symbol = 'PEPEUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    signals = []

    for idx in range(20, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        best_score = 0
        for name, dna in archetype_dnas.items():
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > best_score:
                best_score = score
        
        row_1d = df_1d.loc[idx]
        b4_time = row_1d['datetime'] + timedelta(days=1)
        b4_slice = df_4h[df_4h['datetime'] < b4_time]
        if b4_slice.empty: continue
        b4 = b4_slice.iloc[-1]
        
        # V1 FILTERS
        f_dna = (best_score > 0.65)
        f_vol = (row_1d['vol_ratio'] > 2.0)
        f_4h = (b4['rsi'] < 85)
        
        if f_dna and f_vol and f_4h:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            signals.append({
                'date': row_1d['datetime'].date(),
                'score': best_score,
                'is_hit': next_date in dg_dates
            })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"🐸 PEPEUSDT BASELINE DETECTOR V1")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")

    if not sig_df.empty:
        print("\nAll Signal Details:")
        print("-" * 60)
        for _, row in sig_df.iterrows():
            hit_icon = "✅" if row['is_hit'] else "❌"
            print(f"  {row['date']}: DNA={row['score']:.3f} {hit_icon}")

if __name__ == "__main__":
    main()
