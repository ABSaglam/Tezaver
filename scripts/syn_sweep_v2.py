"""
SYNUSDT Unique Strategy Discovery (with Progress)
==================================================
Coin-specific analysis with progress indicators.
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
    symbol = 'SYNUSDT'
    print(f"🔄 Loading {symbol} data...")
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    print(f"✓ {len(all_results)} rallies loaded")
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    print(f"✓ {len(df_1d)} daily candles loaded")
    
    # Calculate indicators
    print("🔄 Calculating indicators...")
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    print("✓ Indicators calculated")
    
    print("\n" + "="*70)
    print(f"🔬 {symbol} THRESHOLD SWEEP")
    print("="*70)
    
    # Test mom_3d thresholds (SYN's best discriminator)
    print("\n📊 mom_3d Sweep:")
    for thresh in [25, 30, 35, 40, 45, 50]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_3d'] >= thresh:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_3d >= {thresh}%: {len(signals)} signals, {hits} hits -> {prec:.1f}%{marker}")
    
    # Test mom_3d + daily_ch combined
    print("\n📊 mom_3d + daily_ch Combined:")
    for m in [25, 30, 35]:
        for d in [10, 15, 20]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['mom_3d'] >= m and row['daily_ch'] >= d:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    res = all_results.get(next_date, ('NONE', 0.0))
                    is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
            
            if signals:
                hits = sum(signals)
                prec = hits / len(signals) * 100
                if prec >= 90:
                    marker = " ✅" if prec == 100 else " 🔶"
                    print(f"  mom_3d >= {m}%, daily >= {d}%: {len(signals)} signals, {hits} hits -> {prec:.1f}%{marker}")
    
    # Test mom_3d + vol_ratio combined
    print("\n📊 mom_3d + vol_ratio Combined:")
    for m in [25, 30, 35]:
        for v in [2.0, 2.5, 3.0]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['mom_3d'] >= m and row['vol_ratio'] >= v:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    res = all_results.get(next_date, ('NONE', 0.0))
                    is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
            
            if signals:
                hits = sum(signals)
                prec = hits / len(signals) * 100
                if prec >= 90:
                    marker = " ✅" if prec == 100 else " 🔶"
                    print(f"  mom_3d >= {m}%, vol >= {v}x: {len(signals)} signals, {hits} hits -> {prec:.1f}%{marker}")
    
    print("\n✅ SYN sweep completed!")

if __name__ == "__main__":
    main()
