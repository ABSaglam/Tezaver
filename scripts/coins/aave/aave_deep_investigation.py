"""
AAVEUSDT Deep Investigation
============================
AAVE shows unique dip-buying pattern but low precision.
Investigating if 100% is achievable or if we should skip this coin.
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
    print(f"🔄 Investigating {symbol}...")
    
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD', 'SILVER')", (symbol,))
    all_results = {pd.to_datetime(json.loads(r[0])['start_time']).date(): (r[1], json.loads(r[0])['gain']) for r in cursor.fetchall()}
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    
    print("\n🔬 Testing ultra-strict negative filters:")
    
    # Test MORE NEGATIVE thresholds
    for daily_t in [-12, -15, -18, -20]:
        signals = []
        for idx in range(25, len(df_1d)-1):
            row = df_1d.loc[idx]
            if row['daily_ch'] <= daily_t:
                next_date = df_1d.loc[idx+1, 'datetime'].date()
                res = all_results.get(next_date, ('NONE', 0.0))
                is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                signals.append(is_hit)
        
        if signals:
            hits = sum(signals)
            prec = hits / len(signals) * 100
            marker = " ✅" if prec == 100 else ""
            print(f"daily_ch <= {daily_t}%: {len(signals)} sig, {hits} hit -> {prec:.1f}%{marker}")
    
    # Test negative + volume spike
    print("\n🔬 Negative daily + volume spike:")
    for daily_t in [-10, -12, -15]:
        for vol_t in [2.0, 3.0, 4.0]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['daily_ch'] <= daily_t and row['vol_ratio'] >= vol_t:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    res = all_results.get(next_date, ('NONE', 0.0))
                    is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
            
            if signals:
                hits = sum(signals)
                prec = hits / len(signals) * 100
                if prec >= 80:
                    marker = " ✅" if prec == 100 else " 🔶"
                    print(f"daily<={daily_t}%, vol>={vol_t}x: {len(signals)} sig, {hits} hit -> {prec:.1f}%{marker}")
    
    # Test negative + positive EMA (oversold but still above EMA)
    print("\n🔬 Negative daily + positive EMA (contrarian):")
    for daily_t in [-10, -12, -15]:
        for ema_t in [0, 5, 10]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['daily_ch'] <= daily_t and row['ema_dist'] >= ema_t:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    res = all_results.get(next_date, ('NONE', 0.0))
                    is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
                    signals.append(is_hit)
            
            if signals:
                hits = sum(signals)
                prec = hits / len(signals) * 100
                if prec >= 80:
                    marker = " ✅" if prec == 100 else " 🔶"
                    print(f"daily<={daily_t}%, ema>={ema_t}%: {len(signals)} sig, {hits} hit -> {prec:.1f}%{marker}")
    
    print("\n✅ Investigation complete!")

if __name__ == "__main__":
    main()
