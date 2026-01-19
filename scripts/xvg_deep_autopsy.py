"""
XVGUSDT Deep Signal Autopsy
=============================
Rallies vs Failures: Let's find the ghost in the machine.
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
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def main():
    # DNA Detector result replication
    dna_path = coin_cell_paths.get_library_root() / "xvg_archetype_dnas.json"
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    df_4h = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

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

    print(f"{'Date':<12} | {'Score':<6} | {'Hit?':<5} | {'1d RSI':<6} | {'4h RSI':<6} | {'VolR':<5}")
    print("-" * 60)

    for idx in range(2, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        best_score = 0
        for name, dna in archetype_dnas.items():
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > best_score:
                best_score = score
        
        if best_score > 0.65:
            sig_date = df_1d.loc[idx, 'datetime'].date()
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            is_hit = next_date in dg_dates
            
            # 4H data for the 6 hours preceding close
            b4 = df_4h[df_4h['datetime'] < (df_1d.loc[idx, 'datetime'] + timedelta(days=1))].iloc[-1]
            
            print(f"{str(sig_date):<12} | {best_score:6.3f} | {is_hit!s:5} | {df_1d.loc[idx]['rsi']:6.1f} | {b4['rsi']:6.1f} | {df_1d.loc[idx]['vol_ratio']:5.1f}")

if __name__ == "__main__":
    main()
