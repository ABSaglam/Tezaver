"""
PEPEUSDT Missing Diamonds Autopsy
==================================
Analyzes why 19 Diamonds were missed by V4.
Goal: Find additional 100% precise paths.
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
    symbol = 'PEPEUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = ? AND tier = 'DIAMOND'", (symbol,))
    all_diamonds = [(pd.to_datetime(json.loads(r[1])['start_time']).date(), r[0]) for r in cursor.fetchall()]
    conn.close()

    # Signals from V4 (dates are signal dates, rally is next day)
    caught_rally_dates = {
        pd.to_datetime('2023-10-26').date(), # Signal was 10-25
        pd.to_datetime('2024-03-06').date(), # Signal was 03-05
        pd.to_datetime('2024-11-15').date()  # Signal was 11-14
    }

    missing = [d for d in all_diamonds if d[0] not in caught_rally_dates]
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    
    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['macd_hist'] = calculate_macd_hist(df_1w['close'])
    df_1w['macd_slope'] = df_1w['macd_hist'] - df_1w['macd_hist'].shift(1)

    print("="*100)
    print(f"🎬 PEPE MISSING {len(missing)} DIAMONDS AUTOPSY")
    print("="*100)

    miss_reasons = {'Bearish_Weekly': 0, 'No_Staircase': 0, 'Low_Relative_Vol': 0}

    for m_date, _ in missing:
        sig_dt = m_date - timedelta(days=1)
        row = df_1d[df_1d['datetime'].dt.date == sig_dt]
        if row.empty: continue
        row = row.iloc[0]
        idx = row.name
        
        v1 = row['volume']
        v2 = df_1d.loc[idx-1, 'volume']
        v3 = df_1d.loc[idx-2, 'volume']
        g2 = v2 / v3
        
        w_row = df_1w[df_1w['datetime'] <= row['datetime']].iloc[-1]
        
        reasons = []
        if w_row['macd_slope'] <= 0:
            reasons.append("Bear_Week")
            miss_reasons['Bearish_Weekly'] += 1
        if g2 <= 1.1:
            reasons.append("Flat_Acc")
            miss_reasons['No_Staircase'] += 1
        
        # Relative Volume to 20d MA
        vol_ma = df_1d.loc[idx-20:idx-1, 'volume'].mean()
        if v1 / vol_ma < 2.0:
            reasons.append("Low_Vol")
            miss_reasons['Low_Relative_Vol'] += 1

    print(f"\nSummary of Miss Reasons:")
    for k, v in miss_reasons.items():
        print(f"  {k}: {v} / {len(missing)}")

if __name__ == "__main__":
    main()
