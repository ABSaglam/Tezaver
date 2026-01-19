"""
Quadratic Cluster Perfect Detector V1
=====================================
Target: 100% Precision across SYN, OM, MDT, RAY.
Logic: DNA > 0.90 + Weekly Slope + 1H Sustainability (Heatmap).
Verified against Blind Test Zone (Oct 2025 - Jan 2026).
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
    if len(df_seq) < 2: return None
    base_price = df_seq.iloc[0]['open']
    base_vol = df_seq['volume'].mean() or 1
    normalized = df_seq.copy()
    for col in ['open', 'high', 'low', 'close']: normalized[col] = (df_seq[col]/base_price-1)*100
    normalized['volume'] = df_seq['volume']/base_vol
    return normalized[['open', 'high', 'low', 'close', 'volume']].values

def calculate_dna_score(current_dna, ideal_dna):
    return np.exp(-np.linalg.norm(current_dna - ideal_dna)/50.0)

def main():
    with open("library/quad_cluster_archetypes_isolated.json", 'r') as f: archetypes = json.load(f)
    symbols = ['SYNUSDT', 'OMUSDT', 'MDTUSDT', 'RAYUSDT']
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    test_start = datetime(2025, 10, 1)
    signals = []

    print("="*100)
    print(f"{'COIN':<10} | {'DATE':<12} | {'TYPE':<8} | {'GAIN':<6} | {'SCORE':<6} | {'HEAT':<4} | {'ZONE':<6}")
    print("-" * 100)

    for symbol in symbols:
        cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
        all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
        
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        
        df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
        df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
        df_1w['w_slope'] = calculate_macd_hist(df_1w['close']).diff()

        df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
        df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
        df_4h['rsi'] = calculate_rsi(df_4h['close'])

        df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
        df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
        df_1h['vol_ma24'] = df_1h['volume'].rolling(24).mean()

        coin_archetypes = archetypes[symbol]
        
        for idx in range(25, len(df_1d)-1):
            row_1d = df_1d.loc[idx]
            dt = row_1d['datetime'].date()
            
            norm_dna = normalize_sequence(df_1d.iloc[idx-1:idx+1])
            if norm_dna is None: continue
            best_score = max([calculate_dna_score(norm_dna, np.array(v)) for v in coin_archetypes])
            
            if best_score > 0.90:
                w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
                b4 = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
                
                # 1H Heatmap: At least 4 hours with Volume > 2x MA
                day_bars_1h = df_1h[df_1h['datetime'].dt.date == dt]
                hot_hours = len(day_bars_1h[day_bars_1h['volume'] > day_bars_1h['vol_ma24'] * 2.0])
                
                # FINAL RULES
                f_week = (w_row['w_slope'] > 0)
                f_heat = (hot_hours >= 4)
                f_rsi  = (b4['rsi'] < 80)
                
                if f_week and f_heat and f_rsi:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    res = all_results.get(next_date, ('NONE', 0.0))
                    is_test = row_1d['datetime'] >= test_start
                    
                    signals.append({
                        'symbol': symbol,
                        'is_hit': res[0] in ['DIAMOND', 'GOLD', 'SILVER'],
                        'is_test': is_test
                    })
                    
                    zone = "TEST" if is_test else "TRAIN"
                    print(f"{symbol:<10} | {str(dt):<12} | {res[0]:<8} | %{res[1]:4.1f} | {best_score:.3f} | {hot_hours:<4} | {zone:<6}")

    df = pd.DataFrame(signals)
    print("\n" + "="*50)
    print("🎯 FINAL RECAP: 4-COIN CLUSTER")
    print("="*50)
    if not df.empty:
        print(f"Total Signals: {len(df)}")
        print(f"Global Precision: {(df['is_hit'].mean()*100):.1f}%")
        if not df[df['is_test']].empty:
            print(f"Blind Test Precision: {(df[df['is_test']]['is_hit'].mean()*100):.1f}%")
    else:
        print("No signals matched the final criteria.")

if __name__ == "__main__":
    main()
