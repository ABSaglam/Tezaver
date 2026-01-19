"""
AAVEUSDT Threshold Sweep
=========================
Tests NEGATIVE thresholds (AAVE's unique dip-buying pattern)
Rally signals come after DECLINES!
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

def main():
    symbol = 'AAVEUSDT'
    print(f"🔄 Loading {symbol}...")
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    print(f"✓ {len(all_results)} rallies")
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    print("✓ Ready")
    
    print("\n" + "="*70)
    print(f"🔬 {symbol} THRESHOLD SWEEP (NEGATIVE VALUES)")
    print("="*70)
    
    # Test NEGATIVE daily_ch (strongest discriminator)
    print("\n📊 daily_ch NEGATIVE Sweep:")
    for thresh in [-10, -8, -6, -4, -2, 0]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['daily_ch'] <= thresh:  # LESS THAN (negative)
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  daily_ch <= {thresh}%: {len(signals)} signals, {hits} hits -> {prec:.1f}%{marker}")
    
    # Test NEGATIVE mom_3d
    print("\n📊 mom_3d NEGATIVE Sweep:")
    for thresh in [-15, -12, -10, -8, -5, 0]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['mom_3d'] <= thresh:  # LESS THAN (negative)
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"  mom_3d <= {thresh}%: {len(signals)} signals, {hits} hits -> {prec:.1f}%{marker}")
    
    # Combined negative filters
    print("\n📊 Combined NEGATIVE Filters:")
    for d in [-6, -5, -4]:
        for m in [-10, -8, -6]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['daily_ch'] <= d and row['mom_3d'] <= m:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    res = all_results.get(next_date, ('NONE', 0.0))
                    is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
            
            if signals:
                hits = sum(signals)
                prec = hits / len(signals) * 100
                if prec >= 90:
                    marker = " ✅" if prec == 100 else " 🔶"
                    print(f"  daily<={d}%, mom_3d<={m}%: {len(signals)} sig, {hits} hit -> {prec:.1f}%{marker}")
    
    print("\n✅ Done!")

if __name__ == "__main__":
    main()
