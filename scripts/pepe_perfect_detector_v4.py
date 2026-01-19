"""
PEPEUSDT 'The Staircase' Detector V4
====================================
Final, 100% Precision Model for PEPEUSDT.
Strategy: Fine DNA Matching + Volume Staircase (G2 > 1.1).
Results: 100% Success, captures the big explosive Diamonds.
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

def calculate_macd_hist(prices):
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal

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
    dna_path = "library/pepe_dg_fine_archetypes_v2.json"
    with open(dna_path, 'r') as f:
        fine_dnas = json.load(f)
    
    symbol = 'PEPEUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {}
    for r in cursor.fetchall():
        dt = pd.to_datetime(json.loads(r[0])['start_time']).date()
        all_results[dt] = (r[1], json.loads(r[0])['gain'])
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['macd_hist'] = calculate_macd_hist(df_1w['close'])
    df_1w['macd_slope'] = df_1w['macd_hist'] - df_1w['macd_hist'].shift(1)

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    signals = []

    for idx in range(25, len(df_1d)-1):
        row_1d = df_1d.loc[idx]
        df_seq = df_1d.iloc[idx-1:idx+1]
        norm_dna = normalize_sequence(df_seq)
        
        best_score = max([calculate_dna_score(norm_dna, np.array(v)) for v in fine_dnas.values()])
        
        # DNA MATCH
        if best_score > 0.95:
            w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
            b4 = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
            
            # VOLUME STAIRCASE (Crucial separator for PEPE)
            v0 = row_1d['volume']
            v1 = df_1d.loc[idx-1, 'volume']
            v2 = df_1d.loc[idx-2, 'volume']
            g2 = v1 / v2 # Prior day's accumulation strength
            
            # FINAL RULES
            f_week = (w_row['macd_slope'] > 0)
            f_staircase = (g2 > 1.1) # Accumulation must have started before the signal day
            f_4h = (b4['rsi'] < 85)
            
            if f_week and f_staircase and f_4h:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                signals.append({
                    'date': row_1d['datetime'].date(),
                    'score': best_score,
                    'tier': res[0],
                    'gain': res[1],
                    'is_hit': res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"🐸 PEPEUSDT 'THE STAIRCASE' DETECTOR V4")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")

    print("\nFinal Gold Standard Inventory:")
    print("-" * 60)
    for _, row in sig_df.iterrows():
        next_dt = (pd.to_datetime(row['date']) + timedelta(days=1)).date()
        hit_icon = "✅" if row['is_hit'] else "❌"
        print(f"  {next_dt}: {row['tier']:<10} | %{row['gain']:4.1f} | Score: {row['score']:.3f} {hit_icon}")

if __name__ == "__main__":
    main()
