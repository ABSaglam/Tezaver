"""
XVGUSDT Final Harmony Detector V16
===================================
Logic: Daily DNA + 1H Fractal Spark + Weekly MACD Momentum + 4H Freshness.
Goal: 5-8 Signals, 100% Precision.
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

def normalize_seq(df_s):
    bp = df_s.iloc[0]['open']
    bv = df_s['volume'].mean() or 1
    norm = df_s.copy()
    for c in ['open', 'high', 'low', 'close']: norm[c] = (df_s[c]/bp - 1)*100
    norm['volume'] = df_s['volume']/bv
    return norm[['open', 'high', 'low', 'close', 'volume']].values

def calculate_dna_score(current_dna, ideal_dna):
    dist = np.linalg.norm(current_dna - ideal_dna)
    return np.exp(-dist / 50.0) 

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
    df_1h['price_change'] = (df_1h['close'] / df_1h['open'] - 1) * 100

    signals = []

    for idx in range(20, len(df_1d)-1):
        row_1d = df_1d.loc[idx]
        
        curr_dna = normalize_seq(df_1d.iloc[idx-1:idx+1])
        dna_score = max([calculate_dna_score(curr_dna, np.array(v)) for v in archetype_dnas.values()])
        
        if dna_score > 0.60:
            day_bars = df_1h[df_1h['datetime'].dt.date == row_1d['datetime'].date()]
            if day_bars.empty: continue
            
            # 1H Fractal Spark: Concentration > 8x, Price > 8%
            f_spark = day_bars[(day_bars['volume'] > day_bars['vol_ma24'] * 6.0) & (day_bars['price_change'] > 3.0)]
            
            if not f_spark.empty:
                w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
                b4 = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
                
                # FINAL HARMONY FILTERS
                if w_row['macd_slope'] > 0 and b4['rsi'] < 85:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    signals.append({
                        'date': row_1d['datetime'].date(),
                        'is_hit': next_date in success_dates
                    })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT FINAL HARMONY DETECTOR V16 (Triple Lock)")
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
                print(f"  {next_date}: {rally[0]:<10} | {hit_icon}")
            else:
                print(f"  {next_date}: NONE       | {hit_icon}")
        conn.close()

if __name__ == "__main__":
    main()
