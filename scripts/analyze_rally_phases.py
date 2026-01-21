#!/usr/bin/env python3
"""
📊 RALLY PHASE VALUE ANALYZER

Ralliyi 3 faza ayırır ve her fazdaki 'Değer'i (PnL hızı) ölçer.
- Faz 1 (0-30): Launch
- Faz 2 (31-60): Climb
- Faz 3 (61-90): Exhaustion

Amacımız: Hangi fazda kalmanın 'değdiğini' bulmak.
"""

import json
import pandas as pd

def analyze_phases():
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
        
    phase_stats = []
    
    for rally in rally_data:
        candles = rally['15m_data']
        prices = [c['close'] for c in candles]
        
        def get_pnl(start_idx, end_idx):
            if start_idx >= len(prices): return 0
            end_idx = min(end_idx, len(prices)-1)
            return (prices[end_idx] / prices[start_idx] - 1) * 100
            
        p1 = get_pnl(0, 30)
        p2 = get_pnl(30, 60)
        p3 = get_pnl(60, 90)
        
        phase_stats.append({
            'date': rally['date'],
            'Launch (0-30)': round(p1, 2),
            'Climb (31-60)': round(p2, 2),
            'Exhaust (61-90)': round(p3, 2),
            'Total': round(p1+p2+p3, 2)
        })

    df = pd.DataFrame(phase_stats)
    print("📈 PHASE-BY-PHASE PNL DISTRIBUTION")
    print("="*60)
    print(df.to_string(index=False))
    print("="*60)
    print("📊 AVERAGES:")
    print(df.mean(numeric_only=True))

if __name__ == "__main__":
    analyze_phases()
