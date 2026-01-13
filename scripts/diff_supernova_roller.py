#!/usr/bin/env python3
"""
ROCKET Early Warning System: Supernova vs Roller
------------------------------------------------
Analyzes the first 4 bars (1 hour) of ROCKET rallies to find features 
that differentiate SUPERNOVA (explosive) from ROLLER (volatile) types.

Metrics analyzed at T+1h (4 bars):
1. Initial Velocity: % Gain in first hour.
2. Volume Surge: Volume of first hour vs 24h average.
3. RSI Impulse: RSI Delta or Slope.
4. Wick Ratio: Quality of the candles (full body vs wicks).
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths

def analyze_early_phase(rally_row):
    """Deep analyze the first 8 bars (2 hours) of a rally."""
    symbol = rally_row['symbol']
    start_date = pd.to_datetime(rally_row['start_date'])
    archetype = rally_row['archetype']
    
    path = coin_cell_paths.get_history_file(symbol, '15m')
    if not path.exists(): return None
    
    try:
        df = pd.read_parquet(path)
        # Find the start index
        # We need exact match or closest
        # start_date is from our previous scan, should match exactly if data hasn't changed
        
        # Optimize search
        # Filter df around date
        mask = (df['datetime'] >= start_date) & (df['datetime'] <= start_date + pd.Timedelta(hours=4))
        rally_slice = df.loc[mask].copy().reset_index(drop=True)
        
        if len(rally_slice) < 8: return None # Need at least 2 hours of data
        
        # Calculate Initial Metrics (T+1h = first 4 bars)
        initial_4 = rally_slice.iloc[:4]
        
        # 1. Velocity (Gain)
        start_price = initial_4.iloc[0]['open']
        end_price_1h = initial_4.iloc[-1]['close']
        gain_1h = (end_price_1h - start_price) / start_price * 100
        
        # 2. Volume Surge (vs 24h avg context would be better, but let's use local relative)
        # For this script we rely on volume trend within the slice as we don't assume context loaded
        # Simple proxy: Vol of 1st bar vs 4th bar? No.
        # Let's check "Explosive Volume": Do all 4 bars have increasing volume?
        vol = initial_4['volume']
        vol_increasing = vol.is_monotonic_increasing
        avg_vol_1h = vol.mean()
        
        # 3. Candle Quality (Full bodies?)
        bodies = (initial_4['close'] - initial_4['open']).abs()
        ranges = (initial_4['high'] - initial_4['low'])
        body_ratio = (bodies / ranges.replace(0, 0.001)).mean()
        
        # 4. RSI (We need context for RSI, assume DF loaded has enough history? No, parquet is full?)
        # Read parquet is full history usually.
        # Find index in full DF
        start_idx = df[df['datetime'] == start_date].index[0]
        
        # Calculate RSI locally for context
        # Slice wider context
        context_df = df.iloc[max(0, start_idx-20):start_idx+4].copy()
        
        delta = context_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi = 100 - (100 / (1 + rs))
        
        initial_rsi = rsi.iloc[-4] # Start of rally
        final_rsi_1h = rsi.iloc[-1] # End of 1st hour
        rsi_delta = final_rsi_1h - initial_rsi
        
        return {
            'archetype': archetype,
            'gain_1h': gain_1h,
            'body_ratio': body_ratio,
            'rsi_start': initial_rsi,
            'rsi_delta_1h': rsi_delta,
            'vol_increasing': vol_increasing
        }
        
    except Exception as e:
        # print(e)
        return None

def main():
    print("🔬 ROCKET: SUPERNOVA vs ROLLER DIFFERENTIATOR")
    print("="*60)
    
    # Load previously classified rallies
    try:
        rallies = pd.read_csv('library/rally_dna/rocket_rally_morphology.csv')
    except:
        print("Run classify_rocket_rallies.py first!")
        return
        
    # Filter for only SUPERNOVA and ROLLER
    target_rallies = rallies[rallies['archetype'].isin(['💥 SUPERNOVA', '🎢 ROLLER'])]
    print(f"Analyzing {len(target_rallies)} rallies (Supernova & Roller)...")
    
    results = []
    
    for _, row in target_rallies.iterrows():
        res = analyze_early_phase(row)
        if res:
            results.append(res)
            
    df = pd.DataFrame(results)
    
    if df.empty:
        print("No analysis data extracted.")
        return

    # Compare Metrics
    print("\n📊 BATTLE OF THE STARTS (First 1 Hour Stats)")
    print("-" * 60)
    
    stats = df.groupby('archetype').agg({
        'gain_1h': ['mean', 'median', 'std'],
        'body_ratio': ['mean'],
        'rsi_start': ['mean'],
        'rsi_delta_1h': ['mean']
    }).round(2)
    
    print(stats.to_markdown())
    
    print("\n💡 KEY DIFFERENTIATORS DETECTED:")
    
    supernova = df[df['archetype'] == '💥 SUPERNOVA']
    roller = df[df['archetype'] == '🎢 ROLLER']
    
    # Heuristic Checks
    # 1. Initial Velocity
    print(f"\n1. VELOCITY (Gain in 1st Hour)")
    print(f"   💥 Supernova avg: {supernova['gain_1h'].mean():.1f}%")
    print(f"   🎢 Roller avg:    {roller['gain_1h'].mean():.1f}%")
    
    # 2. Candle Confidence
    print(f"\n2. INTENTION (Candle Body Ratio)")
    print(f"   💥 Supernova avg: {supernova['body_ratio'].mean():.2f} (Full candles)")
    print(f"   🎢 Roller avg:    {roller['body_ratio'].mean():.2f} (Wick heavy)")
    
    # 3. Momentum Impulse
    print(f"\n3. MOMENTUM (RSI Delta in 1h)")
    print(f"   💥 Supernova avg: +{supernova['rsi_delta_1h'].mean():.1f} RSI points")
    print(f"   🎢 Roller avg:    +{roller['rsi_delta_1h'].mean():.1f} RSI points")
    
    # Save training data for strategy
    df.to_csv('library/rally_dna/rocket_early_features.csv', index=False)
    print("\n📁 Features saved to library/rally_dna/rocket_early_features.csv")

if __name__ == "__main__":
    main()
