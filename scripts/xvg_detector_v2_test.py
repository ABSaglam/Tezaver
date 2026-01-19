"""
XVGUSDT Perfect DNA Detector V2
================================
Targets higher recall by combining DNA similarity with advanced feature synergy.
Rules:
- DNA Score > 0.60 (Slightly relaxed)
- 4H RSI < 85
- Daily Volume Ratio > 4.0x (Relaxed from 7.5x)
- MACD Acceleration > 0 (Added)
- RSI > RSI_EMA7 (Added)
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

def calculate_macd(prices):
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return hist

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
    
    # Advanced Indicators
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['rsi_ema7'] = df_1d['rsi'].ewm(span=7, adjust=False).mean()
    df_1d['macd_hist'] = calculate_macd(df_1d['close'])
    df_1d['macd_acc'] = df_1d['macd_hist'] - df_1d['macd_hist'].shift(1)
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    signals = []
    THRESHOLD = 0.60 # Relaxed from 0.65

    for idx in range(2, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        best_score = 0
        for name, dna in archetype_dnas.items():
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > best_score:
                best_score = score
        
        if best_score > THRESHOLD:
            # Multi-TF Gatekeeping
            b4 = df_4h[df_4h['datetime'] < (df_1d.loc[idx, 'datetime'] + timedelta(days=1))].iloc[-1]
            row = df_1d.loc[idx]
            
            # V2 RULES
            if b4['rsi'] < 85 and row['vol_ratio'] > 4.0:
                # Add Advanced Harmony
                if row['rsi'] > row['rsi_ema7'] and row['macd_acc'] > 0:
                    sig_date = row['datetime'].date()
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    signals.append({
                        'date': sig_date, 
                        'score': best_score, 
                        'is_hit': next_date in dg_dates
                    })

    if not signals:
        print("No signals found with the V2 Filter.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT PERFECT DNA DETECTOR V2 (Advanced Optimization)")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")
    print(f"Recall:       {(len(hits)/len(dg_dates)*100 if dg_dates else 0):.1f}%")

    if not hits.empty:
        print("\nCaptured Rally Details:")
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
                print(f"  {next_date}: {tier:<10} | Gain: %{gain:5.1f} | Score: {row['score']:.3f} {hit_icon}")
            else:
                print(f"  {next_date}: NONE       | Gain: %  0.0 | Score: {row['score']:.3f} {hit_icon}")
        conn.close()

if __name__ == "__main__":
    main()
