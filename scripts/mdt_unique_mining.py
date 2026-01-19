"""
MDTUSDT Unique Character Mining
================================
Mines MDT's unique rally characteristics without any assumptions.
Discovers what makes MDT rallies unique.
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
    
    # Get all DG rallies
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (symbol,))
    rallies = cursor.fetchall()
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    df_1d['rsi'] = df_1d['close'].diff().apply(lambda x: max(x, 0)).rolling(14).mean() / df_1d['close'].diff().abs().rolling(14).mean() * 100
    df_1d['bb_upper'] = df_1d['close'].rolling(20).mean() + 2 * df_1d['close'].rolling(20).std()
    df_1d['bb_lower'] = df_1d['close'].rolling(20).mean() - 2 * df_1d['close'].rolling(20).std()
    df_1d['bb_width'] = (df_1d['bb_upper'] - df_1d['bb_lower']) / df_1d['close'] * 100
    
    rally_features = []
    
    for raw_data, tier in rallies:
        raw = json.loads(raw_data)
        start_time = pd.to_datetime(raw['start_time'])
        signal_date = (start_time - timedelta(days=1)).date()
        
        row = df_1d[df_1d['datetime'].dt.date == signal_date]
        if row.empty: continue
        row = row.iloc[0]
        idx = row.name
        if idx < 25: continue
        
        prev_row = df_1d.loc[idx-1]
        prev2_row = df_1d.loc[idx-2]
        
        # Calculate 3-day momentum
        three_day_ch = (row['close'] / df_1d.loc[idx-2, 'close'] - 1) * 100
        
        rally_features.append({
            'tier': tier,
            'gain': raw['gain'],
            'ema_dist': row['ema_dist'],
            'daily_ch': row['daily_ch'],
            'prev_ch': prev_row['daily_ch'],
            'prev2_ch': prev2_row['daily_ch'],
            'three_day_ch': three_day_ch,
            'vol_ratio': row['vol_ratio'],
            'rsi': row['rsi'],
            'bb_width': row['bb_width']
        })
    
    df = pd.DataFrame(rally_features)
    
    print("="*80)
    print(f"📊 MDTUSDT UNIQUE CHARACTER ANALYSIS")
    print(f"📈 Total DG Rallies: {len(df)}")
    print("="*80)
    
    print("\n🔍 ALL DG RALLIES - Pre-Rally Day Statistics:")
    print(df.describe().loc[['mean', 'min', 'max', '50%', '25%', '75%']])
    
    # What percentage of rallies had positive daily change?
    pos_daily = len(df[df['daily_ch'] > 0])
    print(f"\n📊 Positive Daily Change: {pos_daily}/{len(df)} ({pos_daily/len(df)*100:.0f}%)")
    
    pos_vol = len(df[df['vol_ratio'] >= 2.0])
    print(f"📊 Volume >= 2x: {pos_vol}/{len(df)} ({pos_vol/len(df)*100:.0f}%)")
    
    pos_ema = len(df[df['ema_dist'] > 0])
    print(f"📊 Positive EMA Distance: {pos_ema}/{len(df)} ({pos_ema/len(df)*100:.0f}%)")
    
    # What about 3-day momentum?
    pos_3d = len(df[df['three_day_ch'] > 10])
    print(f"📊 3-Day Momentum > 10%: {pos_3d}/{len(df)} ({pos_3d/len(df)*100:.0f}%)")
    
    conn.close()

if __name__ == "__main__":
    main()
