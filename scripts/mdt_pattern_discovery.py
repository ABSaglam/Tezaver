"""
MDTUSDT Pattern Discovery
=========================
Explores MDT-specific patterns that differentiate rally days from non-rally days.
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

def main():
    symbol = 'MDTUSDT'
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    # Get all DG rally dates
    cursor.execute("SELECT raw_data FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
    rallies = cursor.fetchall()
    rally_signal_dates = set()
    for raw_data, in rallies:
        raw = json.loads(raw_data)
        start_time = pd.to_datetime(raw['start_time'])
        signal_date = (start_time - timedelta(days=1)).date()
        rally_signal_dates.add(signal_date)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    # Bollinger Band Squeeze
    df_1d['bb_mid'] = df_1d['close'].rolling(20).mean()
    df_1d['bb_std'] = df_1d['close'].rolling(20).std()
    df_1d['bb_squeeze'] = df_1d['close'] / df_1d['bb_std']
    
    # 5-day momentum
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    
    # Weekly high proximity
    df_1d['weekly_high_prox'] = (df_1d['high'].rolling(7).max() - df_1d['close']) / df_1d['close'] * 100
    
    # Mark rally days vs non-rally days
    rally_features = []
    non_rally_features = []
    
    for idx in range(25, len(df_1d)):
        row = df_1d.loc[idx]
        sig_date = row['datetime'].date()
        
        entry = {
            'ema_dist': row['ema_dist'],
            'daily_ch': row['daily_ch'],
            'vol_ratio': row['vol_ratio'],
            'bb_squeeze': row['bb_squeeze'],
            'mom_5d': row['mom_5d'],
            'weekly_high_prox': row['weekly_high_prox']
        }
        
        if sig_date in rally_signal_dates:
            rally_features.append(entry)
        else:
            non_rally_features.append(entry)
    
    rally_df = pd.DataFrame(rally_features)
    non_rally_df = pd.DataFrame(non_rally_features)
    
    print("="*90)
    print(f"📊 MDTUSDT PATTERN DISCOVERY")
    print(f"Rally Days: {len(rally_df)} | Non-Rally Days: {len(non_rally_df)}")
    print("="*90)
    
    print("\n🎯 RALLY DAYS (Pre-Signal) Statistics:")
    print(rally_df.describe().loc[['mean', '50%']])
    
    print("\n❌ NON-RALLY DAYS Statistics:")
    print(non_rally_df.describe().loc[['mean', '50%']])
    
    # Find discriminating thresholds
    print("\n" + "="*60)
    print("🔍 DISCRIMINATING FEATURES")
    print("="*60)
    
    for col in ['ema_dist', 'daily_ch', 'vol_ratio', 'mom_5d']:
        r_mean = rally_df[col].mean()
        nr_mean = non_rally_df[col].mean()
        diff = ((r_mean - nr_mean) / abs(nr_mean) * 100) if nr_mean != 0 else 0
        print(f"{col}: Rally={r_mean:.2f} vs NonRally={nr_mean:.2f} (Diff: {diff:.0f}%)")

if __name__ == "__main__":
    main()
