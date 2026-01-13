#!/usr/bin/env python3
"""
ROCKET Rally Morphologist
-------------------------
Classifies rallies of the ROCKET cluster into behavioral archetypes.

Archetypes:
1. 💥 SUPERNOVA  : Extremely fast, high gain (>30% in <12h).
2. 🚀 LAUNCHPAD  : Fast start (vertical), then plateau.
3. 🪜 STAIRS     : (Merdiven) Slower, consistent higher lows, long duration.
4. 🎢 ROLLER     : High volatility during ascent (deep pullbacks).
5. 🚜 TRACTOR    : Slow grind up, very low speed.

Methodology:
- Load ROCKET coins.
- Extract rallies (Diamond/Gold/Silver) from historical 15m data.
- Analyze:
    - Speed (%/hour)
    - Linearity (R-squared of linear regression on uptrend)
    - Max Drawdown during rally
    - Duration
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import sys
import os
import re

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths

def parse_rallies_from_report(report_path):
    """Parse rallies from report to get specific coins and tiers."""
    with open(report_path, 'r') as f:
        content = f.read()
    
    rallies = []
    # Pattern: SYMBOL(TIER+GAIN%)
    pattern = r'(\w+)\((D|G|S)\+(\d+)%\)'
    
    # We need to map this back to approximate dates if possible, or just scan history 
    # for these magnitude moves to get the exact shape.
    # Since we can't easily parse date from the compact report lines without more context,
    # we will SCAN the 15m history of ROCKET coins for moves matching these magnitudes.
    
    matches = re.findall(pattern, content)
    # Filter for unique symbol-tier combinations to guide our scan
    # Actually, let's just use the ROCKET symbols and find ALL rallies > 5% to classify them.
    return set([m[0] + "USDT" for m in matches])

def get_rocket_symbols():
    try:
        df = pd.read_csv('library/coin_dna/final_classification.csv')
        # Filter for actual ROCKET cluster
        return df[df['cluster_name'] == 'ROCKET']['symbol'].tolist()
    except:
        return []

def classify_shape(price_series):
    """
    Classify the shape of a price series (uptrend).
    Returns: Archetype, Metrics
    """
    if len(price_series) < 4:
        return "UNKNOWN", {}

    # Normalize stats
    start_price = price_series.iloc[0]
    end_price = price_series.iloc[-1]
    peak_price = price_series.max()
    
    total_gain = (end_price - start_price) / start_price * 100
    max_gain = (peak_price - start_price) / start_price * 100
    
    duration_hours = len(price_series) * 0.25
    speed = max_gain / duration_hours # % per hour
    
    # Linearity (Fit a line)
    x = np.arange(len(price_series))
    y = price_series.values
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    linearity = r_value ** 2
    
    # Volatility (Std Dev of residuals from trend line)
    trend_line = slope * x + intercept
    residuals = (y - trend_line) / y
    volatility = np.std(residuals) * 100
    
    # Classification Logic
    archetype = "STANDARD"
    
    if speed > 4.0 and max_gain > 20:
        archetype = "💥 SUPERNOVA"
    elif linearity > 0.85 and speed < 1.5:
        archetype = "🪜 STAIRS"
    elif volatility > 3.0: # High volatility around trend
        archetype = "🎢 ROLLER"
    elif speed > 2.0 and duration_hours < 4:
         archetype = "🚀 LAUNCHPAD" # Fast burst
    elif speed < 0.5:
        archetype = "🚜 TRACTOR"
        
    return archetype, {
        "speed": speed,
        "linearity": linearity,
        "volatility": volatility,
        "duration": duration_hours,
        "gain": max_gain
    }

def scan_and_classify(symbols):
    results = []
    
    print(f"Scanning {len(symbols)} ROCKET coins for rallies...")
    
    for i, symbol in enumerate(symbols):
        if i % 10 == 0: print(f"Processing {i}/{len(symbols)}...", end="\r")
        
        path = coin_cell_paths.get_history_file(symbol, '15m')
        if not path.exists(): continue
        
        try:
            df = pd.read_parquet(path)
            # Find Rallies: Simple algorithm -> Find local minima, then subsequent local maxima > 10% gain
            # Simplified: Rolling min to find start, calculate forward gain
            
            # We will use a simple heuristic to find rallies to classify
            # Look for 4h periods with > 5% gain, then extend
            
            # Optimization: Calculate percentage change over different windows (e.g., 4h, 12h, 24h)
            # Note: This is computationally expensive to do perfectly, so we'll sample high movement periods.
            
            # Detect peaks > 15% relative to 24h low
            df['roll_min'] = df['low'].rolling(96).min() # 24h low
            df['gain_from_low'] = (df['high'] - df['roll_min']) / df['roll_min'] * 100
            
            # Get big moves
            peaks = df[df['gain_from_low'] > 15]
            
            # Dedup peaks (take highest in local window)
            # This logic is a bit crude but sufficient for shape analysis
            processed_ranges = []
            
            for idx, row in peaks.nlargest(10, 'gain_from_low').iterrows(): # Analyze top 10 rallies per coin
                # Find the start point (the low)
                # Search backwards for the minimum
                search_window = df.loc[max(0, idx-96):idx]
                id_min = search_window['low'].idxmin()
                
                # Check overlaps
                is_overlap = False
                for start, end in processed_ranges:
                    if start <= id_min <= end or start <= idx <= end:
                        is_overlap = True
                        break
                if is_overlap: continue
                
                processed_ranges.append((id_min, idx))
                
                # Extract Segment
                segment = df.loc[id_min:idx, 'close']
                
                # Classify
                arch, metrics = classify_shape(segment)
                
                metrics['symbol'] = symbol
                metrics['archetype'] = arch
                metrics['start_date'] = df.loc[id_min, 'datetime']
                results.append(metrics)
                
        except Exception as e:
            # print(f"Error {symbol}: {e}")
            pass

    return pd.DataFrame(results)

def main():
    rocket_symbols = get_rocket_symbols()
    if not rocket_symbols:
        print("No ROCKET symbols found.")
        return

    df = scan_and_classify(rocket_symbols)
    
    print("\n" + "="*60)
    print("🛸 ROCKET RALLY MORPHOLOGY")
    print("="*60)
    
    # Summary
    counts = df['archetype'].value_counts()
    print("\nArchetype Distribution:")
    for arch, count in counts.items():
        pct = count / len(df) * 100
        print(f"  {arch}: {count} ({pct:.1f}%)")
        
    print("\n" + "="*60)
    print("📊 ARCHETYPE CHARACTERISTICS")
    print("="*60)
    
    for arch in counts.index:
        subset = df[df['archetype'] == arch]
        print(f"\n{arch}:")
        print(f"  Avg Speed    : {subset['speed'].mean():.1f}% / hour")
        print(f"  Avg Duration : {subset['duration'].mean():.1f} hours")
        print(f"  Avg Linearity: {subset['linearity'].mean():.2f} (R²)")
        print(f"  Avg Volatility: {subset['volatility'].mean():.2f}")
        
        # Example coins
        top_examples = subset['symbol'].value_counts().head(5).index.tolist()
        print(f"  Top Coins    : {', '.join([s.replace('USDT','') for s in top_examples])}")

    # Save
    output_path = 'library/rally_dna/rocket_rally_morphology.csv'
    df.to_csv(output_path, index=False)
    print(f"\n📁 Saved to {output_path}")

if __name__ == "__main__":
    main()
