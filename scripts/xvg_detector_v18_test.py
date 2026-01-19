"""
XVGUSDT 'The Perfect Clone' Detector V18
=========================================
Final refinement of the Fine-Grained Archetype strategy.
Goal: 10+ Signals, 100% Precision.
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
    # Load Fine-Grained Archetypes
    dna_path = coin_cell_paths.get_library_root() / "xvg_dg_fine_archetypes_v3.json"
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    # Ground Truth (Success = Tier exists and Gain > 10% or Tier in D,G,S)
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, tier, raw_data FROM rallies WHERE symbol = 'XVGUSDT'")
    all_results = {}
    for r in cursor.fetchall():
        dt = pd.to_datetime(json.loads(r[2])['start_time']).date()
        tier = r[1]
        gain = json.loads(r[2])['gain']
        all_results[dt] = (tier, gain)
    conn.close()

    # Data
    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['macd_hist'] = calculate_macd_hist(df_1w['close'])
    df_1w['macd_slope'] = df_1w['macd_hist'] - df_1w['macd_hist'].shift(1)

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')

    signals = []
    SIMILARITY_THRESHOLD = 0.88 # Slightly tightened from 0.85

    for idx in range(20, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        best_score = 0
        for name, dna in archetype_dnas.items():
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > best_score:
                best_score = score
        
        if best_score > SIMILARITY_THRESHOLD:
            row_1d = df_1d.loc[idx]
            b4 = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
            w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
            
            # 1H Concentration Check
            day_bars_1h = df_1h[df_1h['datetime'].dt.date == row_1d['datetime'].date()]
            concentration = 0
            if not day_bars_1h.empty:
                concentration = day_bars_1h['volume'].max() / day_bars_1h['volume'].sum() if day_bars_1h['volume'].sum() > 0 else 0
            
            # FINAL RULES
            # 1. Weekly MACD Slope > 0
            # 2. 4H RSI < 85
            # 3. 1H Volume Concentration > 15% (Eliminate distributed 'lazy' volume)
            if w_row['macd_slope'] > 0 and b4['rsi'] < 85 and concentration > 0.15:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                
                signals.append({
                    'date': row_1d['datetime'].date(),
                    'score': best_score,
                    'tier': res[0],
                    'gain': res[1],
                    'is_hit': is_hit
                })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT 'THE PERFECT CLONE' DETECTOR V18")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)} (Silver+)")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")

    print("\nVerified Rally List:")
    print("-" * 60)
    for _, row in sig_df.iterrows():
        next_dt = (pd.to_datetime(row['date']) + timedelta(days=1)).date()
        hit_icon = "✅" if row['is_hit'] else "❌"
        print(f"  {next_dt}: {row['tier']:<10} | Gain: %{row['gain']:5.1f} | Score: {row['score']:.3f} {hit_icon}")

if __name__ == "__main__":
    main()
