"""
XVGUSDT Perfect Detector V10 (The Peak)
========================================
Focuses on 'Maximum Force' signals.
Logic: DNA > 0.65 + Vol Growth > 2.5x + Vol is 10-day MAX + 4H RSI cap.
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
    df_1d['vol_max10'] = df_1d['volume'].rolling(10).max()
    
    df_4h = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '4h')).sort_values('timestamp').reset_index(drop=True)
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
        prev_row = df_1d.loc[idx-1]
        b4 = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
        
        # PEAK FILTERS
        f_dna = (best_score > 0.65)
        f_vol_growth = (row_1d['volume'] > prev_row['volume'] * 5.0) # Intense acceleration
        f_vol_peak = (row_1d['volume'] >= row_1d['vol_max10']) # Local volume peak
        f_4h_rsi = (b4['rsi'] < 80) # Freshness
        
        if f_dna and f_vol_growth and f_vol_peak and f_4h_rsi:
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
    print(f"💎 XVGUSDT PERFECT DETECTOR V10 (The Peak)")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")
    print(f"Recall:       {(len(hits)/len(dg_dates)*100 if dg_dates else 0):.1f}%")

    if not sig_df.empty:
        print("\nSignal Log:")
        print("-" * 60)
        for _, row in sig_df.iterrows():
            next_dt = (pd.to_datetime(row['date']) + timedelta(days=1)).date()
            hit_icon = "✅" if row['is_hit'] else "❌"
            print(f"  {next_dt}: DNA={row['score']:.3f} | {hit_icon}")

if __name__ == "__main__":
    main()
