"""
XVGUSDT Weekly MACD Momentum Audit (V9 Signals)
==============================================
Analyzes the Weekly MACD/Signal slope for V9 signals.
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

def main():
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_dates = set([pd.to_datetime(json.loads(r[1])['start_time']).date() for r in cursor.fetchall()])
    conn.close()

    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')

    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['macd_hist'] = calculate_macd_hist(df_1w['close'])
    df_1w['macd_slope'] = df_1w['macd_hist'] - df_1w['macd_hist'].shift(1)

    # Simplified V9-like logic (Volume Growth > 2.2)
    signals = []
    for idx in range(20, len(df_1d)-1):
        row_1d = df_1d.loc[idx]
        prev_row = df_1d.loc[idx-1]
        
        if row_1d['volume'] > prev_row['volume'] * 2.2:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            is_hit = next_date in dg_dates
            
            w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
            
            signals.append({
                'date': row_1d['datetime'].date(),
                'w_macd_slope': w_row['macd_slope'],
                'is_hit': is_hit
            })

    df = pd.DataFrame(signals)
    hits = df[df['is_hit']]
    fails = df[~df['is_hit']]
    
    print("="*80)
    print("🔬 WEEKLY MACD MOMENTUM: HITS VS FAILS")
    print("="*80)
    
    # Analyze Hits
    print(f"Hits ({len(hits)}):")
    h_pos = (hits['w_macd_slope'] > 0).sum()
    print(f"  Pos Slope: {h_pos} / {len(hits)} ({h_pos/len(hits)*100:.1f}%)")
    
    # Analyze Fails
    print(f"Fails ({len(fails)}):")
    f_pos = (fails['w_macd_slope'] > 0).sum()
    print(f"  Pos Slope: {f_pos} / {len(fails)} ({f_pos/len(fails)*100:.1f}%)")
    
    # Discovery
    print("\n[Discovery]")
    logic = (df['w_macd_slope'] > 0)
    subset = df[logic]
    if not subset.empty:
        s_hits = subset[subset['is_hit']]
        print(f"Filter (Weekly MACD Slope > 0) Precision: {len(s_hits)/len(subset)*100:.1f}%")

if __name__ == "__main__":
    main()
