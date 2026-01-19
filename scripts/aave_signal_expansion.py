"""
AAVEUSDT Signal Expansion
==========================
Finding more signals with daily_ch <= -15% (5 signals, 80%)
Adding filters to reach 100%
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
    print(f"🔄 Expanding {symbol} signals...")
    
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
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    
    # First identify the 5 signals at -15% and their characteristics
    hits = []
    fails = []
    
    for idx in range(25, len(df_1d)-1):
        row = df_1d.loc[idx]
        prev_row = df_1d.loc[idx-1]
        
        if row['daily_ch'] <= -15:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            res = all_results.get(next_date, ('NONE', 0.0))
            is_hit = res[0] in ['DIAMOND', 'GOLD', 'SILVER']
            
            entry = {
                'date': row['datetime'].date(),
                'daily': row['daily_ch'],
                'vol': row['vol_ratio'],
                'ema': row['ema_dist'],
                'mom_3d': row['mom_3d'],
                'prev_daily': prev_row['daily_ch']
            }
            
            if is_hit: hits.append(entry)
            else: fails.append(entry)
    
    print(f"\n📊 At daily_ch <= -15%: {len(hits)} hits, {len(fails)} fails")
    print("\nHITS:")
    for h in hits:
        print(f"  {h['date']}: daily={h['daily']:.1f}%, vol={h['vol']:.1f}x, ema={h['ema']:.1f}%, mom_3d={h['mom_3d']:.1f}%")
    
    print("\nFAILS:")
    for f in fails:
        print(f"  {f['date']}: daily={f['daily']:.1f}%, vol={h['vol']:.1f}x, ema={f['ema']:.1f}%, mom_3d={f['mom_3d']:.1f}%")
    
    # Test additional filters
    print("\n🔬 Testing filters to eliminate fails:")
    
    for vol_t in [1.0, 1.5, 2.0, 2.5]:
        pass_h = len([h for h in hits if h['vol'] >= vol_t])
        pass_f = len([f for f in fails if f['vol'] >= vol_t])
        total = pass_h + pass_f
        prec = pass_h / total * 100 if total > 0 else 0
        if prec >= 80:
            marker = " ✅" if prec == 100 else " 🔶"
            print(f"vol >= {vol_t}x: {pass_h} hits, {pass_f} fails -> {prec:.0f}%{marker}")
    
    for ema_t in [-10, -5, 0, 5]:
        pass_h = len([h for h in hits if h['ema'] >= ema_t])
        pass_f = len([f for f in fails if f['ema'] >= ema_t])
        total = pass_h + pass_f
        prec = pass_h / total * 100 if total > 0 else 0
        if prec >= 80:
            marker = " ✅" if prec == 100 else " 🔶"
            print(f"ema >= {ema_t}%: {pass_h} hits, {pass_f} fails -> {prec:.0f}%{marker}")
    
    for mom_t in [-20, -15, -10, -5, 0]:
        pass_h = len([h for h in hits if h['mom_3d'] <= mom_t])
        pass_f = len([f for f in fails if f['mom_3d'] <= mom_t])
        total = pass_h + pass_f
        prec = pass_h / total * 100 if total > 0 else 0
        if prec >= 80:
            marker = " ✅" if prec == 100 else " 🔶"
            print(f"mom_3d <= {mom_t}%: {pass_h} hits, {pass_f} fails -> {prec:.0f}%{marker}")

if __name__ == "__main__":
    main()
