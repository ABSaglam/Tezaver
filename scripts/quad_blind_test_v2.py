"""
Quadratic Cluster Blind-Test Discovery (V2)
===========================================
Lowers DNA threshold to 0.70 to see all candidates in the Test Zone.
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
    with open("library/quad_cluster_archetypes_isolated.json", 'r') as f: 
        archetypes = json.load(f)
    symbols = ['SYNUSDT', 'OMUSDT', 'MDTUSDT', 'RAYUSDT']
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    test_start = datetime(2025, 10, 1)
    results = []

    print("="*100)
    print(f"{'COIN':<10} | {'DATE':<12} | {'SCORE':<8} | {'STATUS':<10} | {'WEEKLY':<10} | {'ZONE':<10}")
    print("-" * 100)

    for symbol in symbols:
        cursor.execute("SELECT raw_data FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
        dg_dates = set([pd.to_datetime(json.loads(r[0])['start_time']).date() for r in cursor.fetchall()])
        
        df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
        df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
        
        df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
        df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
        df_1w['w_hist'] = calculate_macd_hist(df_1w['close'])
        df_1w['w_slope'] = df_1w['w_hist'] - df_1w['w_hist'].shift(1)

        coin_archetypes = archetypes[symbol]
        
        for idx in range(25, len(df_1d)-1):
            row_1d = df_1d.loc[idx]
            dt = row_1d['datetime'].date()
            
            # Focus ONLY on Test Zone or strong Train signals
            is_test_zone = row_1d['datetime'] >= test_start
            
            norm_dna = normalize_sequence(df_1d.iloc[idx-1:idx+1])
            if norm_dna is None: continue
            best_score = max([calculate_dna_score(norm_dna, np.array(v)) for v in coin_archetypes])
            
            w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
            
            # Lower threshold for Discovery
            if best_score > 0.75:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                is_hit = next_date in dg_dates
                zone_label = "TEST" if is_test_zone else "TRAIN"
                status = "✅ HIT" if is_hit else "❌ FAIL"
                w_status = "BULL" if w_row['w_slope'] > 0 else "BEAR"
                
                # Show all Test Zone signals, and only Bullish Train signals
                if is_test_zone or w_status == "BULL":
                    if is_test_zone:
                        results.append({
                            'symbol': symbol,
                            'is_hit': is_hit,
                            'is_test_zone': is_test_zone,
                            'score': best_score
                        })
                        print(f"{symbol:<10} | {str(dt):<12} | {best_score:.3f} | {status:<10} | {w_status:<10} | {zone_label:<10}")

    df = pd.DataFrame(results)
    print("\n" + "="*50)
    print("🌍 BLIND TEST SUMMARY (Oct 2025 - Jan 2026)")
    print("="*50)
    if not df.empty:
        print(f"Total Test Signals: {len(df)}")
        print(f"Test Precision:    {(df['is_hit'].mean()*100):.1f}%")
        print("\nBreakdown by Coin (Test Zone):")
        print(df.groupby('symbol')['is_hit'].agg(['count', 'mean', 'sum']))
    else:
        print("Still no signals in Test Zone. Threshold might be too high for these specific coins.")

if __name__ == "__main__":
    main()
