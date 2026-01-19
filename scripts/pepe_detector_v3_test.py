"""
PEPEUSDT sustainable Heat Detector V3
======================================
Logic: DNA > 0.95 + 1H Heatmap (Sustained Momentum) + EMA Gradient.
Goal: 50%+ Precision, 100% Success for Diamonds.
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
    return (std * 4) / sma if not (sma == 0).any() else pd.Series(0, index=prices.index)

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
    if not os.path.exists(dna_path):
        print("DNA archetypes missing.")
        return
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    symbol = 'PEPEUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['bb_width'] = calculate_bb_width(df_1d['close'])
    df_1d['bb_sq'] = df_1d['bb_width'] / df_1d['bb_width'].rolling(10).mean()

    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['macd_hist'] = calculate_macd_hist(df_1w['close'])
    df_1w['macd_slope'] = df_1w['macd_hist'] - df_1w['macd_hist'].shift(1)

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])
    df_4h['ema9'] = df_4h['close'].ewm(span=9, adjust=False).mean()
    df_4h['ema_grad'] = (df_4h['ema9'] / df_4h['ema9'].shift(1) - 1) * 100

    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
    df_1h['vol_ma24'] = df_1h['volume'].rolling(24).mean()

    signals = []

    for idx in range(25, len(df_1d)-1):
        df_seq = df_1d.iloc[idx-1:idx+1]
        current_dna = normalize_sequence(df_seq)
        
        best_score = max([calculate_dna_score(current_dna, np.array(v)) for v in archetype_dnas.values()])
        
        if best_score > 0.95:
            row_1d = df_1d.loc[idx]
            w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
            b4 = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
            
            # 1H Heatmap: How many hours today had Volume > 1.5x MA?
            day_bars_1h = df_1h[df_1h['datetime'].dt.date == row_1d['datetime'].date()]
            hot_hours = len(day_bars_1h[day_bars_1h['volume'] > day_bars_1h['vol_ma24'] * 1.5])
            
            # V3 FILTERS
            f_week = (w_row['macd_slope'] > 0)
            f_grad = (b4['ema_grad'] > 0.5) # Minimum 4H acceleration
            f_heat = (hot_hours >= 6) # Sustained interest
            f_4h = (b4['rsi'] < 85)
            
            if f_week and f_grad and f_heat and f_4h:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                signals.append({
                    'date': row_1d['datetime'].date(),
                    'score': best_score,
                    'hot_h': hot_hours,
                    'is_hit': next_date in dg_dates
                })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"🐸 PEPEUSDT SUSTAINABLE HEAT DETECTOR V3")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")

    if not sig_df.empty:
        print("\nAll Signal Details:")
        print("-" * 60)
        for _, row in sig_df.iterrows():
            hit_icon = "✅" if row['is_hit'] else "❌"
            print(f"  {row['date']}: DNA={row['score']:.3f} | HotH={row['hot_h']} {hit_icon}")

if __name__ == "__main__":
    main()
