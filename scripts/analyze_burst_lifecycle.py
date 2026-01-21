#!/usr/bin/env python3
"""
⚡ BURST LIFE CYCLE ANALYZER (FLASH RESEARCH)

Bir ralli 'Turbo' moduna girdiğinde, o yüksek hız ne kadar sürüyor?
Amacımız: 40 mum beklemek yerine, 15-20 mumda işi bitiren 'Flash' ASM'yi tasarlamak.

- Burst başladıktan sonraki PnL/Zaman eğrisi.
- Marjinal getirinin (diminishing returns) başladığı mum.
"""

import json
import pandas as pd
import numpy as np

def analyze_burst_lifecycle():
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    
    # 5-candle velocity based trigger to identify burst start
    results = []
    
    for rally in rally_data:
        candles = rally['15m_data']
        prices = [c['close'] for c in candles]
        
        burst_start_idx = None
        for i in range(5, len(prices)):
            vel_5c = (prices[i] / prices[i-5] - 1) * 100
            if vel_5c > 2.0: # Burst detected
                burst_start_idx = i
                break
        
        if burst_start_idx:
            # Measure PnL after 10, 20, 30 candles
            pnl_10 = (prices[min(burst_start_idx+10, len(prices)-1)] / prices[burst_start_idx] - 1) * 100
            pnl_20 = (prices[min(burst_start_idx+20, len(prices)-1)] / prices[burst_start_idx] - 1) * 100
            pnl_30 = (prices[min(burst_start_idx+30, len(prices)-1)] / prices[burst_start_idx] - 1) * 100
            
            results.append({
                'date': rally['date'],
                'start': burst_start_idx,
                'pnl_10': round(pnl_10, 2),
                'pnl_20': round(pnl_20, 2),
                'pnl_30': round(pnl_30, 2)
            })

    df = pd.DataFrame(results)
    print("⚡ BURST LIFE CYCLE: PNL AFTER X CANDLES")
    print("="*60)
    print(df.to_string(index=False))
    print("="*60)
    print("📊 AVERAGES (Incremental Gains):")
    print(f"Avg PnL after 10 candles: {df['pnl_10'].mean():.2f}%")
    print(f"Avg PnL after 20 candles: {df['pnl_20'].mean():.2f}%")
    print(f"Avg PnL after 30 candles: {df['pnl_30'].mean():.2f}%")

if __name__ == "__main__":
    analyze_burst_lifecycle()
