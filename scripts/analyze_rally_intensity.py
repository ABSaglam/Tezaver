#!/usr/bin/env python3
"""
🚀 RALLY VELOCITY & INTENSITY ANALYZER

26 rallinin 'en yoğun' (en hızlı yükseldiği) bölgesini bulur.
Amacımız: 80-90 mum beklemek yerine, ralli 'şiştiği' anda çıkmak.

- 10 mumluk pencerelerde maksimum Velocity (PnL / Time)
- Yoğunluk bölgesinin başlangıç ve bitiş mumları
- Bu bölgeden sonra 'yavaşlama' (Grind) ne zaman başlıyor?
"""

import json
import pandas as pd
import numpy as np

def analyze_intensity():
    # 1. Load Data
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    
    print("🔬 Finding the 'Momentum Sweet Spot' (Intensive Regions)...")
    print("="*90)
    print(f"{'DATE':12} | {'START':6} | {'END':6} | {'VELOCITY':8} | {'CORE PNL':8} | {'TOTAL PNL':8}")
    print("-" * 90)
    
    intensities = []
    
    for rally in rally_data:
        candles = rally['15m_data']
        prices = [c['close'] for c in candles]
        
        # Sliding window of 10 candles to find maximum velocity
        window_size = 10
        max_vel = -999
        best_window = (0, 0)
        
        for i in range(len(prices) - window_size):
            p_start = prices[i]
            p_end = prices[i + window_size]
            vel = (p_end / p_start - 1) * 100
            
            if vel > max_vel:
                max_vel = vel
                best_window = (i, i + window_size)
        
        core_pnl = max_vel
        total_pnl = (max(prices) / prices[0] - 1) * 100
        
        res = {
            'date': rally['date'],
            'core_start': best_window[0],
            'core_end': best_window[1],
            'velocity_10c': round(core_pnl, 2),
            'total_pnl': round(total_pnl, 2)
        }
        intensities.append(res)
        
        print(f"{res['date']:12} | C{res['core_start']:2}    | C{res['core_end']:2}    | {res['velocity_10c']:5.2f}%/10c | {res['velocity_10c']:6.2f}% | {res['total_pnl']:7.2f}%")

    # Aggregated Stats
    df = pd.DataFrame(intensities)
    print("="*90)
    print(f"📊 INTENSITY AGGREGATED INSIGHTS")
    print(f"Average Core Start: C{df['core_start'].mean():.1f}")
    print(f"Average Core End:   C{df['core_end'].mean():.1f}")
    print(f"Average Core PnL:   {df['velocity_10c'].mean():.2f}%")
    print(f"Most Frequent Start Zone: {df['core_start'].value_counts().idxmax()} (C{df['core_start'].value_counts().index[0]})")
    
    # Save to JSON
    with open("data/algo_rally_intensity_map.json", "w") as f:
        json.dump(intensities, f, indent=2)

if __name__ == "__main__":
    analyze_intensity()
