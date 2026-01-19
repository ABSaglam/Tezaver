"""
XVGUSDT Weekly Launching Pad & Volume Velocity Analysis
========================================================
Finds the 'Triple Lock' conditions for all 46 DG rallies.
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
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    dg_rallies = [(pd.to_datetime(json.loads(r[1])['start_time']), json.loads(r[1])['gain']) for r in cursor.fetchall()]
    conn.close()

    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    
    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['rsi'] = calculate_rsi(df_1w['close'])

    print("="*100)
    print("📈 XVGUSDT TRIPLE LOCK ANALYSIS (Weekly + Vol Acceleration)")
    print("="*100)
    
    results = []
    for rally_time, gain in dg_rallies:
        # 1. Weekly State at rally start
        w_row = df_1w[df_1w['datetime'] <= rally_time].iloc[-1]
        
        # 2. Daily Vol Velocity (last 3 days)
        idx = df_1d[df_1d['datetime'] < rally_time].index[-1]
        v_0 = df_1d.loc[idx, 'volume']
        v_1 = df_1d.loc[idx-1, 'volume']
        v_2 = df_1d.loc[idx-2, 'volume']
        
        # Volume Growth Ratio
        growth_ratio = v_0 / v_1 if v_1 > 0 else 1
        acceleration = growth_ratio / (v_1 / v_2) if v_2 > 0 and v_1 > 0 else 1
        
        results.append({
            'time': rally_time,
            'gain': gain,
            'w_rsi': w_row['rsi'],
            'v_growth': growth_ratio,
            'v_accel': acceleration
        })

    df = pd.DataFrame(results)
    print(f"Total DG analyzed: {len(df)}")
    print(f"\nWeekly RSI Range: {df['w_rsi'].min():.1f} - {df['w_rsi'].max():.1f}")
    print(f"Avg Vol Growth: {df['v_growth'].mean():.2f}")
    print(f"Avg Vol Accel: {df['v_accel'].mean():.2f}")

    # Now let's try a "Perfect Logic" discovery
    print("\n[Discovery Path]")
    # Condition A: Vol Growth > 2.0 AND Weekly RSI between 45-75
    logic_a = (df['v_growth'] > 2.0) & (df['w_rsi'] > 45) & (df['w_rsi'] < 75)
    print(f"Condition (Vol Growth > 2 & W_RSI 45-75) captured {len(df[logic_a])} DG rallies.")
    
    # Let's see if this Condition A ever happens for FAILURES
    # We need to run this against the FULL history and check for "False Positives"
    
if __name__ == "__main__":
    main()
