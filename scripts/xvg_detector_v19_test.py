"""
XVGUSDT Ultimate Hybrid Detector V19
=====================================
A Committee of Experts:
1. 'The Hammer' (Explosive Volume + Basic DNA)
2. 'The Mirror' (Near-Perfect Fine DNA Match)
3. 'The Sonic' (1H Micro-Pulse + BB Squeeze)

Goal: Maximize signal count with 100% Precision.
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

def calculate_bb_width(prices, window=20):
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    return (std * 4) / sma

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
    # Load Fine Archetypes
    dna_path = coin_cell_paths.get_library_root() / "xvg_dg_fine_archetypes_v3.json"
    with open(dna_path, 'r') as f:
        fine_dnas = json.load(f)
    
    # Ground Truth
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = 'XVGUSDT'")
    all_results = {}
    for r in cursor.fetchall():
        dt = pd.to_datetime(json.loads(r[0])['start_time']).date()
        all_results[dt] = (r[1], json.loads(r[0])['gain'])
    conn.close()

    # Data
    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['volume'].rolling(20).mean()
    df_1d['bb_width'] = calculate_bb_width(df_1d['close'])
    df_1d['bb_sq'] = df_1d['bb_width'] / df_1d['bb_width'].rolling(10).mean()

    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['macd_hist'] = calculate_macd_hist(df_1w['close'])
    df_1w['macd_slope'] = df_1w['macd_hist'] - df_1w['macd_hist'].shift(1)

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
    df_1h['vol_ma24'] = df_1h['volume'].rolling(24).mean()
    df_1h['price_ch'] = (df_1h['close'] / df_1h['open'] - 1) * 100

    signals = []

    for idx in range(25, len(df_1d)-1):
        row_1d = df_1d.loc[idx]
        df_seq = df_1d.iloc[idx-1:idx+1]
        norm_dna = normalize_sequence(df_seq)
        
        best_score = max([calculate_dna_score(norm_dna, np.array(v)) for v in fine_dnas.values()])
        
        # Expert 1: THE HAMMER (High Vol)
        # Proven 100% precision in V1
        f1_vol = row_1d['vol_ratio'] > 7.5
        f1_4h = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]['rsi'] < 85
        is_hammer = (best_score > 0.65) and f1_vol and f1_4h
        
        # Expert 2: THE MIRROR (Perfect Match)
        # Extreme DNA match + Positive Weekly
        w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
        is_mirror = (best_score > 0.94) and (w_row['macd_slope'] > 0)
        
        # Expert 3: THE SONIC (1H Micro-Pulse)
        # BB Squeeze + 1H Explosion
        day_bars_1h = df_1h[df_1h['datetime'].dt.date == row_1d['datetime'].date()]
        f3_pulse = not day_bars_1h[(day_bars_1h['volume'] > day_bars_1h['vol_ma24'] * 7.5) & (day_bars_1h['price_ch'] > 7.5)].empty
        is_sonic = (row_1d['bb_sq'] < 0.70) and f3_pulse and (best_score > 0.70)

        if is_hammer or is_mirror or is_sonic:
            path_label = "HAMMER" if is_hammer else ("MIRROR" if is_mirror else "SONIC")
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            res = all_results.get(next_date, ('NONE', 0.0))
            signals.append({
                'date': row_1d['datetime'].date(),
                'path': path_label,
                'tier': res[0],
                'gain': res[1],
                'is_hit': res[0] in ['DIAMOND', 'GOLD', 'SILVER'],
                'score': best_score
            })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT ULTIMATE COMMITTEE V19 (The Perfectionist)")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)} (Silver+)")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")

    print("\nFinal Rally Inventory (100% Target):")
    print("-" * 60)
    for _, row in sig_df.iterrows():
        next_dt = (pd.to_datetime(row['date']) + timedelta(days=1)).date()
        hit_icon = "✅" if row['is_hit'] else "❌"
        print(f"  {next_dt}: {row['tier']:<10} | %{row['gain']:4.1f} | Path: {row['path']:<8} | Score: {row['score']:.3f} {hit_icon}")

if __name__ == "__main__":
    main()
