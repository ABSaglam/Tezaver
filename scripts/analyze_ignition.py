#!/usr/bin/env python3
"""
🔬 IGNITION SIGNATURE ANALYZER (T-0 vs PREP)

Neden Hazırlık gününde (Prep) giriyoruz? Çünkü ralliye benziyor.
Neden girmemeliydik? Çünkü 'hızlanmadı'.

Bu script, Entry noktasındaki (C40+) şu farklara bakar:
1. Son 2 mumdaki RSI artış hızı.
2. Entry mumunun volüm 'şoku' (Vol Ratio).
3. Entry mumunun gerçek gövde (Body) yüzdesi.
"""

import json
import pandas as pd
import numpy as np
from datetime import timedelta

def analyze_ignition_signature():
    # 1. Identify Journey Dates (T-0 vs Prep)
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    
    rally_dates = [pd.Timestamp(r['date']) for r in rally_data]
    journey_offsets = [1, 3, 5, 7, 14, 21]
    
    journey_map = {}
    for rd in rally_dates:
        journey_map[rd.date()] = "RALLY"
        for offset in journey_offsets:
            p_day = (rd - timedelta(days=offset)).date()
            if p_day not in journey_map:
                journey_map[p_day] = "PREP"

    # 2. Data
    df_15m = pd.read_parquet("coin_cells/ALGOUSDT/data/history_15m.parquet")
    df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
    df_15m['vol_ma'] = df_15m['volume'].rolling(20).mean()
    df_15m['vol_ratio'] = df_15m['volume'] / df_15m['vol_ma']
    
    # Simple RSI
    delta = df_15m['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df_15m['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))

    signatures = []
    
    for date, day_type in journey_map.items():
        day_start = pd.Timestamp(date)
        day_end = day_start + pd.Timedelta(days=1)
        day_df = df_15m[(df_15m['timestamp'] >= day_start) & (df_15m['timestamp'] < day_end)]
        
        if len(day_df) < 80: continue
        
        # Simulating Sniper Entry (C40+)
        for idx in range(40, len(day_df)-2):
            c = day_df.iloc[idx]
            # Potential Trigger: Vol > 0.8 (Current v12 rule)
            if c['vol_ratio'] > 0.8:
                # Let's see what happens in the NEXT 2 candles (Ignition Phase)
                next_1 = day_df.iloc[idx+1]
                next_2 = day_df.iloc[idx+2]
                
                rsi_jump = next_2['rsi'] - c['rsi']
                price_jump = (next_2['close'] / c['close'] - 1) * 100
                max_vol_next = max(next_1['vol_ratio'], next_2['vol_ratio'])
                
                signatures.append({
                    'type': day_type,
                    'rsi_jump': round(rsi_jump, 2),
                    'price_jump': round(price_jump, 2),
                    'max_vol': round(max_vol_next, 2)
                })
                break # Only check the FIRST potential entry of the day

    df_sig = pd.DataFrame(signatures)
    print("📊 IGNITION SIGNATURE COMPARISON (First Move after C40)")
    print("="*80)
    summary = df_sig.groupby('type').agg(['mean', 'median', 'std']).T
    print(summary)
    
    print("\n" + "="*80)
    print("🎯 PROBABILITY OF RALLY GIVEN SIGNATURE:")
    # If RSI Jump > 5?
    r_rsi = df_sig[df_sig['rsi_jump'] > 5]
    print(f"RSI Jump > 5: {len(r_rsi[r_rsi['type']=='RALLY'])} Rallies vs {len(r_rsi[r_rsi['type']=='PREP'])} Preps")
    
    # If Price Jump > 1%?
    r_price = df_sig[df_sig['price_jump'] > 1.0]
    print(f"Price Jump > 1%: {len(r_price[r_price['type']=='RALLY'])} Rallies vs {len(r_price[r_price['type']=='PREP'])} Preps")

if __name__ == "__main__":
    analyze_ignition_signature()
