"""
XVGUSDT Perfect DNA Detector V5 (Double-Spark)
==============================================
Requires volume acceleration, Weekly MACD support, and tight 4H freshness.
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

def calculate_macd_hist(prices):
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal

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
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    df_1w = pd.read_parquet(coin_cell_paths.get_history_file('XVGUSDT', '1w')).sort_values('timestamp')
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['macd_hist'] = calculate_macd_hist(df_1w['close'])

    signals = []

    for idx in range(5, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        best_score = 0
        for name, dna in archetype_dnas.items():
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > best_score:
                best_score = score
        
        row = df_1d.loc[idx]
        prev_row = df_1d.loc[idx-1]
        
        # DOUBLE-SPARK RULES
        
        # 1. DNA Floor
        if best_score < 0.60: continue
        
        # 2. Volume Acceleration
        # Must have high volume AND it must be higher than previous day
        f_vol = (row['vol_ratio'] > 6.0) and (row['volume'] > prev_row['volume'] * 1.5)
        
        # 3. 4H Check (Even tighter RSI)
        b4 = df_4h[df_4h['datetime'] < (row['datetime'] + timedelta(days=1))].iloc[-1]
        f_4h = b4['rsi'] < 80
        
        # 4. Weekly Context
        # Must be in a supportive weekly trend (MACD rising)
        w_row = df_1w[df_1w['datetime'] <= row['datetime']].iloc[-1]
        prev_w = df_1w[df_1w['datetime'] <= row['datetime'] - timedelta(days=7)].iloc[-1]
        f_weekly = w_row['macd_hist'] > prev_w['macd_hist']
        
        if f_vol and f_4h and f_weekly:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            signals.append({
                'date': row['datetime'].date(), 
                'score': best_score, 
                'is_hit': next_date in dg_dates
            })

    if not signals:
        print("No signals found with Double-Spark.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT PERFECT DNA DETECTOR V5 (Double-Spark)")
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
                print(f"  {next_date}: {tier:<10} | %{gain:5.1f} | Score: {row['score']:.3f} {hit_icon}")
            else:
                print(f"  {next_date}: NONE       | %  0.0 | Score: {row['score']:.3f} {hit_icon}")
        conn.close()

if __name__ == "__main__":
    main()
