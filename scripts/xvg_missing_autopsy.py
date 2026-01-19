"""
XVGUSDT Missing 41 DG Autopsy
==============================
Analyzes the Diamond/Gold rallies missed by V11.
Finds why they were missed and how to catch them safely.
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
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT event_time, raw_data FROM rallies WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD')")
    all_dg = [(pd.to_datetime(json.loads(r[1])['start_time']).date(), r[0]) for r in cursor.fetchall()]
    conn.close()

    # Dates caught by V11 (from output)
    caught = {
        pd.to_datetime('2023-06-28').date(),
        pd.to_datetime('2023-07-03').date(),
        pd.to_datetime('2023-07-04').date(),
        pd.to_datetime('2025-05-13').date(),
        pd.to_datetime('2025-10-02').date()
    }

    missing = [d for d in all_dg if d[0] not in caught]
    
    symbol = 'XVGUSDT'
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d')).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    
    df_1w = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1w')).sort_values('timestamp').reset_index(drop=True)
    df_1w['datetime'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
    df_1w['macd_hist'] = calculate_macd_hist(df_1w['close'])
    df_1w['macd_slope'] = df_1w['macd_hist'] - df_1w['macd_hist'].shift(1)

    print("="*100)
    print(f"🎬 MISSING 41 DG AUTOPSY: ANALYZING WHY THEY FAILED V11")
    print("="*100)

    miss_reasons = {'Low_Vol_Growth': 0, 'Bearish_Weekly': 0, 'Low_DNA': 0}
    
    # Reload V11 Archetypes for DNA check
    dna_path = coin_cell_paths.get_library_root() / "xvg_dg_archetypes_v2.json"
    with open(dna_path, 'r') as f:
        archetype_dnas = json.load(f)

    for m_date, _ in missing:
        # Signal day is m_date - 1 day
        sig_dt = m_date - timedelta(days=1)
        row = df_1d[df_1d['datetime'].dt.date == sig_dt]
        if row.empty: continue
        row = row.iloc[0]
        idx = row.name
        
        prev_row = df_1d.loc[idx-1]
        vol_growth = row['volume'] / prev_row['volume']
        
        w_row = df_1w[df_1w['datetime'] <= row['datetime']].iloc[-1]
        w_slope = w_row['macd_slope']
        
        # DNA Check
        def normalize_seq(df_s):
            bp = df_s.iloc[0]['open']
            bv = df_s['volume'].mean() or 1
            norm = df_s.copy()
            for c in ['open', 'high', 'low', 'close']: norm[c] = (df_s[c]/bp - 1)*100
            norm['volume'] = df_s['volume']/bv
            return norm[['open', 'high', 'low', 'close', 'volume']].values
            
        curr_dna = normalize_seq(df_1d.iloc[idx-1:idx+1])
        dna_score = max([np.exp(-np.linalg.norm(curr_dna - np.array(v))/50.0) for v in archetype_dnas.values()])

        reasons = []
        if vol_growth <= 3.0: 
            reasons.append("Low_Vol")
            miss_reasons['Low_Vol_Growth'] += 1
        if w_slope <= 0: 
            reasons.append("Bear_Week")
            miss_reasons['Bearish_Weekly'] += 1
        if dna_score <= 0.60: 
            reasons.append("Low_DNA")
            miss_reasons['Low_DNA'] += 1
            
        # print(f"  {m_date}: {', '.join(reasons)} | Vol={vol_growth:.1f}x | W_Slope={w_slope:.4f} | DNA={dna_score:.3f}")

    print(f"\nSummary of Miss Reasons (Note: Multiple reasons possible per rally):")
    for k, v in miss_reasons.items():
        print(f"  {k}: {v} / {len(missing)}")

if __name__ == "__main__":
    main()
