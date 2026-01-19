"""
XVGUSDT Trend-Only Detector V12
===============================
Ignores DNA shapes. Focuses on 'Clean Trend' crossovers.
Logic: 1D RSI > 50 + 4H MACD Cross Up + Weekly Context.
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
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()

    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h')).sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h['macd_hist'] = calculate_macd_hist(df_4h['close'])
    
    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['rsi'] = calculate_rsi(df_1w['close'])

    signals = []

    for idx in range(20, len(df_1d)-1):
        row_1d = df_1d.loc[idx]
        prev_row_1d = df_1d.loc[idx-1]
        
        # TREND CROSSOVER FILTERS
        
        # 1. Daily: RSI just crossed 50 or is strong (>55)
        f_daily = (row_1d['rsi'] > 55) and (row_1d['close'] > row_1d['ema9'])
        
        # 2. 4H: MACD Histogram just turned positive
        b4_time = row_1d['datetime'] + timedelta(days=1)
        b4_slice = df_4h[df_4h['datetime'] < b4_time]
        if len(b4_slice) < 2: continue
        b4 = b4_slice.iloc[-1]
        prev_b4 = b4_slice.iloc[-2]
        f_4h = (b4['macd_hist'] > 0) and (prev_b4['macd_hist'] <= 0) # The Cross
        
        # 3. Weekly: Must be in a launchpad (RSI 45-75)
        w_row = df_1w[df_1w['datetime'] <= row_1d['datetime']].iloc[-1]
        f_weekly = (w_row['rsi'] > 50) and (w_row['rsi'] < 80)
        
        if f_daily and f_4h and f_weekly:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            signals.append({
                'date': row_1d['datetime'].date(),
                '1d_rsi': row_1d['rsi'],
                'is_hit': next_date in dg_dates
            })

    if not signals:
        print("No signals found.")
        return

    sig_df = pd.DataFrame(signals)
    hits = sig_df[sig_df['is_hit']]
    
    print("\n" + "="*80)
    print(f"💎 XVGUSDT TREND DETECTOR V12 (Golden Cross)")
    print("="*80)
    print(f"Total Signals: {len(sig_df)}")
    print(f"Correct Hits:  {len(hits)}")
    print(f"Precision:    {(len(hits)/len(sig_df)*100):.1f}%")

    if not sig_df.empty:
        print("\nAll Signal Details:")
        print("-" * 60)
        conn = sqlite3.connect('library/rallies.db')
        for _, row in sig_df.iterrows():
            next_date = (pd.to_datetime(row['date']) + timedelta(days=1)).date()
            cursor = conn.cursor()
            cursor.execute("SELECT tier, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND event_time LIKE ?", (f"{next_date}%",))
            rally = cursor.fetchone()
            hit_icon = "✅" if row['is_hit'] else "❌"
            if rally:
                print(f"  {next_date}: {rally[0]:<10} | RSI={row['1d_rsi']:.1f} {hit_icon}")
            else:
                print(f"  {next_date}: NONE       | RSI={row['1d_rsi']:.1f} {hit_icon}")
        conn.close()

if __name__ == "__main__":
    main()
