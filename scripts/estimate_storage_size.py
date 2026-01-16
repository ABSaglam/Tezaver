#!/usr/bin/env python3
"""
Storage Size Estimator (The 'Big Data' Calculator)
--------------------------------------------------
Calculates the exact disk space required to store:
1. ALL Binance Spot Coins (441+ symbols)
2. ALL Historical Data (from Listing Date to Now)
3. 1-Minute Resolution (1m)
4. FULL Feature Set (Indicators, Rallies, Flags)

Methodology:
1. Scan local 15m data to calculate 'Total Coin-Years' (Sum of all active durations).
2. Generate a 'Mock 1m Year' dataframe with all expected columns (OHLCV + 15 Indicators).
3. Save to Parquet to measure the REAL compressed size.
4. Extrapolate: Total GB = (Size per Year) * (Total Coin-Years).
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def get_total_market_duration():
    """Scans local files to find out how many 'years of data' we actually have."""
    print("⏳ Scanning market age...")
    total_days = 0
    coin_count = 0
    
    # We use the existing 15m or 1d files to estimate start dates
    # If a coin lists in 2020, we need 5 years of 1m data.
    
    # Quick scan of what we have locally
    base_dir = Path("data/coin_cells")
    coins = [f.name for f in base_dir.iterdir() if f.is_dir()]
    
    for symbol in coins:
        path = base_dir / symbol / "history" / "15m.parquet"
        if path.exists():
            try:
                # Read only start/end
                # Reading metadata is faster, but let's just read columns=['datetime']
                # Actually for speed let's just assume we have 1d files?
                # No, audit showed 1d missing. We must use 15m.
                # Optimization: Read first and last row?
                # Pandas parquet read doesn't support head/tail efficiently without reading footer.
                # We will read the whole index.
                df = pd.read_parquet(path, columns=['datetime'])
                if not df.empty:
                    start = df['datetime'].min()
                    end = df['datetime'].max()
                    duration = (end - start).days
                    total_days += duration
                    coin_count += 1
            except:
                pass
                
    years = total_days / 365
    print(f"   Found {coin_count} coins with data.")
    print(f"   Total Market History: {years:.1f} Coin-Years")
    return years, coin_count

def measure_1m_density():
    """Generates a realistic 1-year 1m dataframe and measures size."""
    print("\n⚖️  Measuring data density (Mocking 1 Year of 1m data)...")
    
    # 1 Year in minutes = 365 * 24 * 60 = 525,600 rows
    rows = 525600
    
    # Create Mock Data
    dates = pd.date_range(start='2024-01-01', periods=rows, freq='1min')
    
    # Random floats (Float64 is standard for price, but Parquet compresses well)
    # We'll use Float32 for indicators to save space, Float64 for Price/Vol
    data = {
        'datetime': dates,
        'open': np.random.rand(rows) * 1000,
        'high': np.random.rand(rows) * 1000,
        'low': np.random.rand(rows) * 1000,
        'close': np.random.rand(rows) * 1000,
        'volume': np.random.rand(rows) * 10000,
        
        # INDICATORS (The heavy part)
        'rsi_14': np.random.rand(rows).astype('float32') * 100,
        'atr_14': np.random.rand(rows).astype('float32') * 10,
        'ema_50': np.random.rand(rows).astype('float32') * 1000,
        'ema_200': np.random.rand(rows).astype('float32') * 1000,
        'macd': np.random.rand(rows).astype('float32'),
        'macd_signal': np.random.rand(rows).astype('float32'),
        'macd_hist': np.random.rand(rows).astype('float32'),
        'bollinger_u': np.random.rand(rows).astype('float32') * 1000,
        'bollinger_l': np.random.rand(rows).astype('float32') * 1000,
        'stoch_k': np.random.rand(rows).astype('float32') * 100,
        'stoch_d': np.random.rand(rows).astype('float32') * 100,
        
        # RALLY METADATA
        'rally_id': [f"RALLY_{i//100}" if i%1000 < 100 else None for i in range(rows)], # Sparse strings
        'is_supernova': np.random.choice([True, False], rows), # Boolean
        'trend_status': np.random.choice(['BULL', 'BEAR', 'FLAT'], rows), # Categorical
    }
    
    df = pd.DataFrame(data)
    
    # Convert object to category for efficiency
    df['rally_id'] = df['rally_id'].astype('string') # Or category
    df['trend_status'] = df['trend_status'].astype('category')
    
    # Save test file
    test_file = Path("temp_1m_test.parquet")
    df.to_parquet(test_file, engine='pyarrow', compression='snappy')
    
    size_mb = test_file.stat().st_size / (1024 * 1024)
    print(f"   1 Year of rich 1m data (Compressed): {size_mb:.2f} MB")
    
    # Cleanup
    test_file.unlink()
    
    return size_mb

def main():
    print("🧮 CLOUD STORAGE CALCULATOR")
    print("=" * 60)
    
    # 1. Total Years
    try:
        # Since scanning all files locally might verify sluggish, let's use a heuristic based on knowns
        # or do a partial scan. 
        # FULL SCAN for accuracy.
        total_years, coins = get_total_market_duration()
    except Exception as e:
        print(f"Error scanning: {e}")
        # Fallback estimates
        coins = 500
        total_years = 500 * 3 # Average 3 years per coin
        print(f"   Using Estimate: {total_years} Coin-Years")

    # 2. Size per Year
    mb_per_year = measure_1m_density()
    
    # 3. Calculation
    total_raw_1m_gb = (total_years * mb_per_year) / 1024
    
    # Add Overhead for Derived TFs (5m, 15m, 1h, 4h, 1d)
    # 15m is 1/15th size. 5m is 1/5th. 1h is 1/60th.
    # Sum of fractions: 1/5 + 1/15 + 1/60 + 1/240 + 1/1440 ~= 0.3 (30% overhead)
    derived_gb = total_raw_1m_gb * 0.3
    
    total_gb = total_raw_1m_gb + derived_gb
    
    print("\n📊 FINAL ESTIMATE (Full Market History)")
    print("-" * 60)
    print(f"Total Active Coins: {coins}")
    print(f"Total Market History: {total_years:.0f} years (cumulative)")
    print(f"Size per Coin-Year (1m + Features): {mb_per_year:.2f} MB")
    print("-" * 60)
    print(f"Raw 1m Data:       {total_raw_1m_gb:.2f} GB")
    print(f"Derived TFs Cache: {derived_gb:.2f} GB")
    print(f"Safety Buffer (10%): {(total_gb * 0.1):.2f} GB")
    print("-" * 60)
    print(f"🚀 GRAND TOTAL:     {(total_gb * 1.1):.2f} GB")
    print("=" * 60)
    
    # Reccomendation
    print("\n💡 SERVER RECOMMENDATION:")
    req = total_gb * 1.1
    if req < 35:
        print("   ✅ Standard VPS (40GB Disk) is sufficient.")
    elif req < 75:
        print("   ⚠️ Upgrade needed: High-End VPS (80GB Disk).")
    else:
        print("   🛑 Big Data Territory: Need Dedicated Volume (100GB+).")

if __name__ == "__main__":
    main()
