"""
3-Coin Extended Threshold Sweep
===============================
Higher thresholds for 100% precision on SYN, OM, RAY.
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

def sweep_coin(symbol, primary_col, thresholds):
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    
    print(f"\n🔬 {symbol} EXTENDED SWEEP ({primary_col} focus)")
    print("-" * 60)
    
    for thresh in thresholds:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row[primary_col] >= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                signals.append({'is_hit': is_hit})
        
        df = pd.DataFrame(signals)
        if not df.empty:
            prec = df['is_hit'].mean() * 100
            hits = df['is_hit'].sum()
            marker = "✅" if prec == 100 else ""
            print(f"{primary_col} >= {thresh}%: {len(df)} signals, {hits} hits -> {prec:.1f}% {marker}")
    
    # Try combined with daily_ch
    print(f"\n--- {symbol} + Daily Change ---")
    for thresh in thresholds[:3]:
        for daily_t in [10, 15, 20]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row[primary_col] >= thresh and row['daily_ch'] >= daily_t:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    res = all_results.get(next_date, ('NONE', 0.0))
                    is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append({'is_hit': is_hit})
            
            df = pd.DataFrame(signals)
            if not df.empty:
                prec = df['is_hit'].mean() * 100
                hits = df['is_hit'].sum()
                if prec >= 95:
                    marker = "✅" if prec == 100 else "🔶"
                    print(f"{primary_col} >= {thresh}%, daily >= {daily_t}%: {len(df)} signals, {hits} hits -> {prec:.1f}% {marker}")

def main():
    print("="*80)
    print("🎯 EXTENDED THRESHOLD SWEEP FOR 100% PRECISION")
    print("="*80)
    
    sweep_coin('SYNUSDT', 'mom_3d', [30, 35, 40, 45, 50])
    sweep_coin('OMUSDT', 'ema_dist', [25, 30, 35, 40, 45])
    sweep_coin('RAYUSDT', 'ema_dist', [25, 30, 35, 40, 45])

if __name__ == "__main__":
    main()
