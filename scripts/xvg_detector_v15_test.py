"""
XVGUSDT Fractal Spark Detector V15
===================================
Logic: Success = SILVER, GOLD, or DIAMOND.
Strategy: 1H Extreme Pulse (Vol > 5x, Price > 5%) within a Daily DNA setup.
Goal: 5+ Signals, 100% Precision.
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

def main():
    dna_path = coin_cell_paths.get_library_root() / "xvg_dg_archetypes_v2.json"
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD', 'SILVER')")
    success_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
    df_1h['vol_ma24'] = df_1h['volume'].rolling(24).mean()
    df_1h['price_change'] = (df_1h['close'] / df_1h['open'] - 1) * 100

    def calculate_dna_score(current_dna, ideal_dna):
        dist = np.linalg.norm(current_dna - ideal_dna)
        return np.exp(-dist / 50.0) 

    def normalize_seq(df_s):
        bp = df_s.iloc[0]['open']
        bv = df_s['volume'].mean() or 1
        norm = df_s.copy()
        for c in ['open', 'high', 'low', 'close']: norm[c] = (df_s[c]/bp - 1)*100
        norm['volume'] = df_s['volume']/bv
        return norm[['open', 'high', 'low', 'close', 'volume']].values

    signals = []

    for idx in range(20, len(df_1d)-1):
        row_1d = df_1d.loc[idx]
        
        # Daily DNA Match (even weak 0.55)
        curr_dna = normalize_seq(df_1d.iloc[idx-1:idx+1])
        best_score = max([calculate_dna_score(curr_dna, np.array(v)) for v in archetype_dnas.values()])
        
        if best_score > 0.55:
            # Check for 1H Fractal Spark on this day
            day_bars = df_1h[df_1h['datetime'].dt.date == row_1d['datetime'].date()]
            if day_bars.empty: continue
            
            # THE FRACTAL SPARK: Vol > 8x AND Price > 8% in a SINGLE hour
            f_spark = day_bars[(day_bars['volume'] > day_bars['vol_ma24'] * 8.0) & (day_bars['price_change'] > 8.0)]
            
            if not f_spark.empty:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                signals.append({
                    'date': row_1d['datetime'].date(),
                    'score': best_score,
                    'is_hit': next_date in success_dates
                })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT FRACTAL SPARK DETECTOR V15 (1H Pulse)")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)} (Gain > 10%)")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")

    if not sig_df.empty:
        conn = sqlite3.connect('library/rallies.db')
        for _, row in sig_df.iterrows():
            next_date = (pd.to_datetime(row['date']) + timedelta(days=1)).date()
            cursor = conn.cursor()
            cursor.execute("SELECT tier, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND event_time LIKE ?", (f"{next_date}%",))
            rally = cursor.fetchone()
            hit_icon = "✅" if row['is_hit'] else "❌"
            if rally:
                print(f"  {next_date}: {rally[0]:<10} | Hit={hit_icon}")
            else:
                print(f"  {next_date}: NONE       | Hit={hit_icon}")
        conn.close()

if __name__ == "__main__":
    main()
