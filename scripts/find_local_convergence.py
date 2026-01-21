#!/usr/bin/env python3
"""
🔭 15M CONVERGENCE FINDER (THE LOCAL SPARK)

Rallinin yoğun bölgesi (Burst) başlamadan hemen önce 15M EMAlar 'öpüşüyor' mu?
Amacımız: C50-60 civarındaki o sessiz sıkışmayı yakalamak.

- Burst öncesi 15M EMA9/21/50 Compression ölçümü.
- Burst öncesi Bollinger Band daralması (isteğe bağlı).
"""

import json
import pandas as pd
import numpy as np

def find_local_convergence():
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    with open("data/algo_rally_intensity_map.json", 'r') as f:
        intensity_map = json.load(f)
        
    print("🔬 Checking 15M EMA Convergence 1-3 candles BEFORE the Burst...")
    print("="*90)
    print(f"{'DATE':12} | {'BURST':6} | {'COMP@START':10} | {'MIN_COMP_5C':12} | {'EMA_READY'}")
    print("-" * 90)
    
    convergence_data = []
    
    for i, rally in enumerate(rally_data):
        c_start = intensity_map[i]['core_start']
        if c_start < 10: continue
        
        # Calculate context for each candle
        def get_comp(c):
            emas = [c.get('ema9', 0), c.get('ema21', 0), c.get('ema50', 0)]
            if 0 in emas: return 999
            return (max(emas) / min(emas) - 1) * 100

        # Comp at exact start
        comp_at_start = get_comp(rally['15m_data'][c_start])
        
        # Min comp in last 5 candles before start
        pre_5_candles = rally['15m_data'][c_start-5:c_start]
        min_comp_last_5 = min(get_comp(c) for c in pre_5_candles)
        
        # EMA alignment
        curr = rally['15m_data'][c_start]
        ema_ready = curr.get('ema9', 0) > curr.get('ema50', 0) # Basic health
        
        convergence_data.append({
            'date': rally['date'],
            'comp_start': round(comp_at_start, 2),
            'min_comp_5c': round(min_comp_last_5, 2),
            'ready': ema_ready
        })
        
        print(f"{rally['date']:12} | C{c_start:2}    | {comp_at_start:8.2f}% | {min_comp_last_5:10.2f}% | {ema_ready}")

    # Insights
    df = pd.DataFrame(convergence_data)
    print("="*90)
    print(f"Average Compression at Burst Start: {df['comp_start'].mean():.2f}%")
    print(f"Average Min Compression (Last 5c): {df['min_comp_5c'].mean():.2f}%")
    print(f"Rallies with Compression < 0.5% before Burst: {sum(df['min_comp_5c'] < 0.5)} / {len(df)}")

if __name__ == "__main__":
    find_local_convergence()
