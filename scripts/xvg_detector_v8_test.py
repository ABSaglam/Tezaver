"""
XVGUSDT Dual-Soul Detector V8
==============================
Path 1: 'The Exploder' (High Vol / Momentum)
Path 2: 'The Squeezer' (Low Vol / Stealth)
Goal: Capture 5-7 rallies with 100% precision.
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
    # Load Archetypes
    dna_path = coin_cell_paths.get_library_root() / "xvg_dg_archetypes_v2.json"
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    # Ground Truth
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    # Data
    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['volume'].rolling(20).mean()
    df_1d['bb_width'] = calculate_bb_width(df_1d['close'])
    df_1d['bb_squeeze'] = df_1d['bb_width'] / df_1d['bb_width'].rolling(10).mean()

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')

    signals = []

    for idx in range(20, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        best_score = 0
        best_arch = ""
        for name, dna in archetype_dnas.items():
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > best_score:
                best_score = score
                best_arch = name
        
        row_1d = df_1d.loc[idx]
        b4 = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
        
        # 1H Micro-context
        day_bars_1h = df_1h[df_1h['datetime'].dt.date == row_1d['datetime'].date()]
        if day_bars_1h.empty: continue
        concentration = day_bars_1h['volume'].max() / day_bars_1h['volume'].sum() if day_bars_1h['volume'].sum() > 0 else 0
        
        # SOUL 1: THE EXPLODER
        # High DNA match, high volume, concentrated volume spark
        is_exploder = (best_score > 0.65) and (row_1d['vol_ratio'] > 5.5) and (concentration > 0.25) and (b4['rsi'] < 85)
        
        # SOUL 2: THE SQUEEZER
        # Extreme DNA match for specific archetypes OR intense squeeze + price tick
        # Let's target the ARCH_1 and ARCH_5 which showed promise
        is_squeezer = (best_score > 0.85 and (best_arch in ['ARCH_1', 'ARCH_3', 'ARCH_5'])) and (row_1d['bb_squeeze'] < 0.75) and (b4['rsi'] < 75)

        if is_exploder or is_squeezer:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            signals.append({
                'date': row_1d['datetime'].date(),
                'path': 'EXPLODER' if is_exploder else 'SQUEEZER',
                'is_hit': next_date in dg_dates,
                'score': best_score
            })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT DUAL-SOUL DETECTOR V8 (The Exploder & The Squeezer)")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")
    print(f"Recall:       {(len(hits)/len(dg_dates)*100 if dg_dates else 0):.1f}%")

    if not sig_df.empty:
        print("\nAll Signal Details:")
        print("-" * 60)
        conn = sqlite3.connect('library/rallies.db')
        for _, row in sig_df.iterrows():
            next_date = (pd.to_datetime(row['date']) + timedelta(days=1)).date()
            cursor = conn.cursor()
            cursor.execute("SELECT tier, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND event_time LIKE ?", (f"{next_date}%",))
            rally = cursor.fetchone()
            hit_icon = "✅" if row['is_hit'] else "❌"
            if rally:
                tier, raw_data = rally
                gain = json.loads(raw_data)['gain']
                print(f"  {next_date}: {tier:<10} | %{gain:5.1f} | Path: {row['path']:<10} | Score: {row['score']:.3f} {hit_icon}")
            else:
                cursor.execute("SELECT tier, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND event_time LIKE ? AND tier = 'SILVER'", (f"{next_date}%",))
                silver = cursor.fetchone()
                if silver:
                    gain = json.loads(silver[1])['gain']
                    print(f"  {next_date}: SILVER     | %{gain:5.1f} | Path: {row['path']:<10} | Score: {row['score']:.3f} {hit_icon}")
                else:
                    print(f"  {next_date}: NONE       | %  0.0 | Path: {row['path']:<10} | Score: {row['score']:.3f} {hit_icon}")
        conn.close()

if __name__ == "__main__":
    main()
