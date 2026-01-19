"""
XVGUSDT Ultra-Sonic Detector V7
================================
Multi-Stage Validation: Daily DNA -> 4H Health -> 1H Micro-Spark.
Goal: Increase signal count while maintaining 100% precision.
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
    # Load 6 Archetype DNAs
    dna_path = coin_cell_paths.get_library_root() / "xvg_dg_archetypes_v2.json"
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    # Ground Truth
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    # Load All Timeframes
    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])
    df_4h['macd_hist'] = calculate_macd_hist(df_4h['close'])

    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
    df_1h['vol_ma24'] = df_1h['volume'].rolling(24).mean() # 1 day avg

    signals = []
    DNA_THRESHOLD = 0.55 # Lower threshold to catch more candidates

    for idx in range(2, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1] # PRE-rally days
        current_dna = normalize_sequence(df_seq)
        
        best_score = 0
        for name, dna in archetype_dnas.items():
            score = calculate_dna_score(current_dna, np.array(dna))
            if score > best_score:
                best_score = score
        
        if best_score > DNA_THRESHOLD:
            row_1d = df_1d.loc[idx]
            
            # STAGE 2: 4H Gatekeeper
            # Find last 4H bar before next day starts
            next_day_start = row_1d['datetime'] + timedelta(days=1)
            b4 = df_4h[df_4h['datetime'] < next_day_start].iloc[-1]
            prev_b4 = df_4h[df_4h['datetime'] < next_day_start].iloc[-2]
            
            f_4h_rsi = b4['rsi'] < 85
            f_4h_macd = b4['macd_hist'] > prev_b4['macd_hist']
            
            if f_4h_rsi and f_4h_macd:
                # STAGE 3: 1H Micro-Spark
                # Look at first 4 hours of the NEXT day (rally start day)
                # Or look at the LAST 4 hours of the current day to see if it's already sparking
                
                # Check for "Front-Running" spark (hours 20-23 of current day)
                spark_bars = df_1h[(df_1h['datetime'] >= next_day_start - timedelta(hours=4)) & 
                                   (df_1h['datetime'] < next_day_start)]
                
                if spark_bars.empty: continue
                
                f_1h_vol = any(spark_bars['volume'] > spark_bars['vol_ma24'] * 2.5)
                f_1h_price = any(spark_bars['close'] > spark_bars['open'] * 1.03)
                
                if f_1h_vol or f_1h_price:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    is_hit = next_date in dg_dates
                    signals.append({
                        'date': row_1d['datetime'].date(), 
                        'score': best_score, 
                        'is_hit': is_hit
                    })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT ULTRA-SONIC DETECTOR V7 (Archetype Expansion)")
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
                # Check if it was a Silver rally
                cursor.execute("SELECT tier, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND event_time LIKE ? AND tier = 'SILVER'", (f"{next_date}%",))
                silver = cursor.fetchone()
                if silver:
                    gain = json.loads(silver[1])['gain']
                    print(f"  {next_date}: SILVER     | %{gain:5.1f} | Score: {row['score']:.3f} {hit_icon}")
                else:
                    print(f"  {next_date}: NONE       | %  0.0 | Score: {row['score']:.3f} {hit_icon}")
        conn.close()

if __name__ == "__main__":
    main()
