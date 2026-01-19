"""
XVGUSDT RSI Harmony Audit (V9 Signals)
=======================================
Analyzes the 49 signals of V9 to find an RSI 'Harmony' that keeps only hits.
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
    if (loss == 0).any(): return pd.Series(50, index=prices.index)
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def main():
    # Load Archetypes
    dna_path = coin_cell_paths.get_library_root() / "xvg_dg_archetypes_v2.json"
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['rsi'] = calculate_rsi(df_1d['close'])

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['rsi'] = calculate_rsi(df_4h['close'])

    df_1h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1h')).sort_values('timestamp').reset_index(drop=True)
    df_1h['datetime'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
    df_1h['rsi'] = calculate_rsi(df_1h['close'])

    signals = []
    # Re-run V9 Logic (Simplified)
    for idx in range(20, len(df_1d)-1):
        row_1d = df_1d.loc[idx]
        prev_row = df_1d.loc[idx-1]
        
        if row_1d['volume'] > prev_row['volume'] * 2.2:
            # Check for ANY V9-like DNA match
            # (Just checking for high volume and some trend for now)
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            is_hit = next_date in dg_dates
            
            b4 = df_4h[df_4h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
            b1 = df_1h[df_1h['datetime'] < (row_1d['datetime'] + timedelta(days=1))].iloc[-1]
            
            signals.append({
                'date': row_1d['datetime'].date(),
                '1d_rsi': row_1d['rsi'],
                '4h_rsi': b4['rsi'],
                '1h_rsi': b1['rsi'],
                'is_hit': is_hit
            })

    df = pd.DataFrame(signals)
    hits = df[df['is_hit']]
    fails = df[~df['is_hit']]
    
    print("="*80)
    print("🔬 RSI HARMONY ANALYSIS: HITS VS FAILS")
    print("="*80)
    print(f"Hits ({len(hits)}):")
    print(f"  1D RSI Range: {hits['1d_rsi'].min():.1f} - {hits['1d_rsi'].max():.1f}")
    print(f"  4H RSI Range: {hits['4h_rsi'].min():.1f} - {hits['4h_rsi'].max():.1f}")
    print(f"  1H RSI Range: {hits['1h_rsi'].min():.1f} - {hits['1h_rsi'].max():.1f}")
    
    # Try to find a filter
    print("\n[Discovery]")
    # Condition: 1D RSI < 65 AND 4H RSI < 85 AND 1H RSI > 50
    logic = (df['1d_rsi'] < 65) & (df['4h_rsi'] < 85) & (df['1h_rsi'] > 50)
    subset = df[logic]
    if not subset.empty:
        s_hits = subset[subset['is_hit']]
        print(f"Filter (1D < 65 & 4H < 85 & 1H > 50) Precision: {len(s_hits)/len(subset)*100:.1f}% ({len(s_hits)} signals)")

    # Condition: 1D RSI BETWEEN 30-55 (Deep Reversal)
    logic_r = (df['1d_rsi'] > 30) & (df['1d_rsi'] < 55)
    subset_r = df[logic_r]
    if not subset_r.empty:
        s_hits_r = subset_r[subset_r['is_hit']]
        print(f"Filter (1D 30-55) Precision: {len(s_hits_r)/len(subset_r)*100:.1f}% ({len(s_hits_r)} signals)")

if __name__ == "__main__":
    main()
