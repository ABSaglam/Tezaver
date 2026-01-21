#!/usr/bin/env python3
"""
⚡ INTENSITY BURST FINDER

Her rallideki 'en yoğun' 5 mumluk (1.25 saat) patlamayı bulur.
Amacımız: Beklemek yerine bu patlamanın tepesinde inmek.
"""

import json
import pandas as pd

def find_bursts():
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
        
    bursts = []
    for rally in rally_data:
        candles = rally['15m_data']
        prices = [c['close'] for c in candles]
        
        # Look for the max 5-candle PnL
        max_pnl = -999
        best_end = 0
        
        for i in range(5, len(prices)):
            pnl = (prices[i] / prices[i-5] - 1) * 100
            if pnl > max_pnl:
                max_pnl = pnl
                best_end = i
        
        total_day_pnl = (max(prices) / prices[0] - 1) * 100
        
        bursts.append({
            'date': rally['date'],
            'burst_end': best_end,
            'burst_pnl': round(max_pnl, 2),
            'total_potential': round(total_day_pnl, 2),
            'efficiency': round(max_pnl / total_day_pnl * 100, 1) if total_day_pnl > 0 else 0
        })

    df = pd.DataFrame(bursts)
    print("🚀 INTENSITY BURST REPORT (5-Candle Windows)")
    print("="*80)
    print(df.to_string(index=False))
    print("="*80)
    print(f"Average Burst End Candle: C{df['burst_end'].mean():.1f}")
    print(f"Average Burst PnL: {df['burst_pnl'].mean():.2f}%")
    print(f"Average Power (Efficiency): {df['efficiency'].mean():.1f}%")

if __name__ == "__main__":
    find_bursts()
