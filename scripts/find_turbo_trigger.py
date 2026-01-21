#!/usr/bin/env python3
"""
⚡ INTENSIVE ENTRY FINDER (TURBO START)

Rallinin en yoğun bölgesinin (genelde C50-60) HEMEN ÖNCESİNDEKİ sinyali arar.
Amacımız: 15 saat beklemek yerine, ralli hızlanırken binmek.

- Hızlanma öncesi Volüm artışı?
- Hızlanma öncesi RSI 60-70 break?
- Hızlanma öncesi EMA9/21/50 genişlemesi?
"""

import json
import pandas as pd
import numpy as np

def find_turbo_trigger():
    # 1. Load data
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    
    with open("data/algo_rally_intensity_map.json", 'r') as f:
        intensity_map = json.load(f)
        
    print("🔬 Analyzing the 10 candles BEFORE the Intensive Region...")
    print("="*90)
    
    triggers = []
    for i, rally in enumerate(rally_data):
        intens = intensity_map[i]
        core_start = intens['core_start'] # e.g., 57
        
        if core_start < 10: continue
        
        # Look at 5-10 candles before the burst
        slice_before = rally['15m_data'][max(0, core_start-10):core_start]
        
        # Metrics to check
        avg_vol_before = sum(c.get('vol_ratio', 0) for c in slice_before) / len(slice_before)
        max_rsi_before = max(c.get('rsi', 0) for c in slice_before)
        
        # Check for a 'Starter Candle' right at core_start or core_start-1
        starter = rally['15m_data'][core_start]
        prev = rally['15m_data'][core_start-1]
        
        # Velocity jump
        v_jump = (starter['close'] / prev['close'] - 1) * 100
        
        triggers.append({
            'date': rally['date'],
            'start': core_start,
            'vol_starter': round(starter.get('vol_ratio', 0), 2),
            'rsi_starter': round(starter.get('rsi', 0), 2),
            'v_jump': round(v_jump, 2),
            'ema_aligned': starter.get('ema9', 0) > starter.get('ema21', 0) > starter.get('ema50', 0)
        })
        
        print(f"📅 {rally['date']} | Start: C{core_start:2} | Vol: {starter.get('vol_ratio', 0):4.2f} | RSI: {starter.get('rsi', 0):4.1f} | Jump: {v_jump:+5.2f}% | EMA: {triggers[-1]['ema_aligned']}")

    # Insights
    df = pd.DataFrame(triggers)
    print("\n" + "="*90)
    print("📊 INTENSIVE ENTRY INSIGHTS")
    print(f"Avg Vol at Start: {df['vol_starter'].mean():.2f}")
    print(f"Avg RSI at Start: {df['rsi_starter'].mean():.1f}")
    print(f"EMA9>21>50 Alignment Rate: {df['ema_aligned'].mean()*100:.1f}%")
    print(f"Min Vol found at Start: {df['vol_starter'].min():.2f}")

if __name__ == "__main__":
    find_turbo_trigger()
