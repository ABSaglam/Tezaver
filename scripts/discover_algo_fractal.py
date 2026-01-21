#!/usr/bin/env python3
"""
🧪 ALGO GOLDEN FRACTAL DISCOVERER

26 rallinin öncesindeki 24 saatlik 1H/4H 'ritmi' inceler.
Bir 'Ahenk' arıyoruz.

- Pre-rally 1H Squeeze (BB tight?)
- Pre-rally 4H State
- RSI Momentum Shift (1H)
- EMA Compression (9,21,50 mesafesi)
"""

import pandas as pd
import json
import numpy as np

def discover_fractal():
    # 1. Load Data
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1.sort_index(inplace=True)
    
    # Add indicators for compression and squeeze
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
    
    # Compression: (Max EMA - Min EMA) / Min EMA
    df_h1['compression'] = (df_h1[['ema9', 'ema21', 'ema50']].max(axis=1) / 
                            df_h1[['ema9', 'ema21', 'ema50']].min(axis=1) - 1) * 100
    
    # RSI
    delta = df_h1['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df_h1['rsi'] = 100 - (100 / (1 + (gain / loss)))
    
    print(f"🔬 Searching for the 'Ahenk' in 26 rallies...")
    print("="*80)
    
    fractal_results = []
    
    for rally in rally_data:
        date_str = rally['date']
        start_ts = pd.to_datetime(rally['15m_data'][0]['timestamp'])
        
        # Look at 24h window before start
        pre_24h = df_h1[(df_h1.index >= start_ts - pd.Timedelta(hours=24)) & (df_h1.index < start_ts)]
        
        if pre_24h.empty:
            continue
            
        # 1. Min Compression (Squeeze) in last 24h
        min_comp = pre_24h['compression'].min()
        
        # 2. RSI Shift
        rsi_start = pre_24h.iloc[0]['rsi']
        rsi_end = pre_24h.iloc[-1]['rsi']
        rsi_shift = rsi_end - rsi_start
        
        # 3. EMA21 Position relative to 50
        ema_cross_imminent = (pre_24h.iloc[-1]['ema9'] > pre_24h.iloc[-1]['ema21']) and \
                             (pre_24h.iloc[-5]['ema9'] <= pre_24h.iloc[-5]['ema21'])
        
        # 4. Volatility (ATR-like)
        volat = (pre_24h['high'] - pre_24h['low']).mean() / pre_24h['close'].mean() * 100
        
        res = {
            'date': date_str,
            'min_comp': round(float(min_comp), 2),
            'rsi_end': round(float(rsi_end), 2),
            'rsi_v_shift': round(float(rsi_shift), 2),
            'volat': round(float(volat), 2),
            'cross': str(ema_cross_imminent)
        }
        fractal_results.append(res)
        
        print(f"📅 {date_str} | Comp: {min_comp:4.1f}% | RSI: {rsi_end:4.1f} (Δ{rsi_shift:+5.1f}) | Volat: {volat:4.1f}% | Cross: {ema_cross_imminent}")

    # Aggregated Insights
    print("\n" + "="*80)
    print("📊 AGGREGATED FRACTAL INSIGHTS")
    print("="*80)
    
    comp_values = [f['min_comp'] for f in fractal_results]
    avg_min_comp = sum(comp_values) / len(comp_values)
    median_min_comp = sorted(comp_values)[len(comp_values)//2]
    
    avg_volat = sum(f['volat'] for f in fractal_results) / len(fractal_results)
    
    print(f"Average Min Compression (Squeeze): {avg_min_comp:.2f}%")
    print(f"Median Min Compression: {median_min_comp:.2f}%")
    print(f"90th Percentile Compression: {sorted(comp_values)[int(len(comp_values)*0.9)]:.2f}%")
    print(f"Average 24h Volatility: {avg_volat:.2f}%")

    with open("data/algo_golden_fractal.json", "w") as f:
        json.dump(fractal_results, f, indent=2)

if __name__ == "__main__":
    discover_fractal()
