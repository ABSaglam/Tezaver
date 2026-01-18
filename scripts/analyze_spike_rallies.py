"""
Flash Crash / Wick Rally Detector
==================================
Detects DSG rallies that start immediately after extreme price spikes/wicks.
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def detect_spike_before_rally(symbol, start_time, lookback_bars=5):
    """
    Detect if there was a sharp price spike/wick before rally start.
    
    Returns:
        dict with spike details or None
    """
    try:
        path = coin_cell_paths.get_history_file(symbol, '15m')
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        df = df.sort_values('timestamp')
        
        # Find rally start bar
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        df['ts_diff'] = (df['timestamp'] - start_ts).abs()
        start_idx = df['ts_diff'].idxmin()
        
        if start_idx < lookback_bars:
            return None
        
        # Look at previous bars
        lookback_start = max(0, start_idx - lookback_bars)
        window = df.iloc[lookback_start:start_idx]
        
        if window.empty:
            return None
        
        # Detect different types of spikes
        spike_detected = False
        spike_type = None
        spike_magnitude = 0
        spike_bar_idx = None
        
        for idx, row in window.iterrows():
            # Type 1: Extreme Wick (long lower tail)
            close_price = row['close']
            low_price = row['low']
            high_price = row['high']
            
            body_size = abs(row['close'] - row['open'])
            total_range = high_price - low_price
            
            if total_range > 0:
                lower_wick = min(row['close'], row['open']) - low_price
                wick_ratio = (lower_wick / total_range) * 100
                drop_pct = ((close_price - low_price) / close_price) * 100
                
                # Extreme wick: lower tail > 60% of candle AND drop > 15%
                if wick_ratio > 60 and drop_pct > 15:
                    if drop_pct > spike_magnitude:
                        spike_detected = True
                        spike_type = 'EXTREME_WICK'
                        spike_magnitude = drop_pct
                        spike_bar_idx = idx
            
            # Type 2: Flash Crash (massive bar-to-bar drop)
            if idx > lookback_start:
                prev_close = df.loc[idx - 1, 'close']
                current_low = row['low']
                flash_drop = ((prev_close - current_low) / prev_close) * 100
                
                if flash_drop > 20:  # 20%+ drop in one bar
                    if flash_drop > spike_magnitude:
                        spike_detected = True
                        spike_type = 'FLASH_CRASH'
                        spike_magnitude = flash_drop
                        spike_bar_idx = idx
        
        if spike_detected:
            # Distance from spike to rally start (in bars)
            distance = start_idx - spike_bar_idx
            
            return {
                'has_spike': True,
                'spike_type': spike_type,
                'spike_magnitude': round(spike_magnitude, 2),
                'bars_after_spike': int(distance)
            }
        
        return {'has_spike': False}
        
    except Exception as e:
        return None

def run_analysis():
    print("=" * 80)
    print(f"📍 FLASH CRASH / WICK RALLY ANALYSIS")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load all DSG rallies
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')"
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    total = len(df_rallies)
    print(f"\nTotal DSG Rallies: {total}\n")
    
    results = []
    
    for i, row in df_rallies.iterrows():
        if (i + 1) % 2000 == 0:
            print(f"Progress: {i+1}/{total} analyzed...")
        
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        symbol = raw_data['symbol']
        start_time = raw_data['start_time']
        tier = row['tier']
        
        spike_info = detect_spike_before_rally(symbol, start_time, lookback_bars=5)
        
        if spike_info:
            spike_info['tier'] = tier
            results.append(spike_info)
    
    if not results:
        print("\n❌ No data")
        return
    
    df = pd.DataFrame(results)
    
    # Statistics
    print("\n" + "=" * 80)
    print("📊 SPIKE RALLY STATISTICS")
    print("=" * 80)
    
    for tier in ['DIAMOND', 'GOLD', 'SILVER']:
        df_tier = df[df['tier'] == tier]
        if df_tier.empty:
            continue
        
        spike_rallies = df_tier[df_tier['has_spike'] == True]
        total_tier = len(df_tier)
        spike_count = len(spike_rallies)
        spike_pct = (spike_count / total_tier) * 100
        
        print(f"\n{'─' * 80}")
        print(f"💎 {tier}")
        print(f"{'─' * 80}")
        print(f"Total Rallies: {total_tier}")
        print(f"Spike Rallies: {spike_count} ({spike_pct:.1f}%)")
        print(f"Normal Rallies: {total_tier - spike_count} ({100-spike_pct:.1f}%)")
        
        if not spike_rallies.empty:
            print(f"\n🔹 SPIKE TYPES:")
            spike_type_counts = spike_rallies['spike_type'].value_counts()
            for stype, count in spike_type_counts.items():
                pct = (count / spike_count) * 100
                avg_mag = spike_rallies[spike_rallies['spike_type'] == stype]['spike_magnitude'].mean()
                print(f"   {stype:20s}: {count:5d} ({pct:5.1f}%) | Avg Drop: {avg_mag:5.1f}%")
            
            print(f"\n🔹 DISTANCE FROM SPIKE:")
            print(f"   Avg Bars After Spike: {spike_rallies['bars_after_spike'].mean():.1f}")
            print(f"   Median: {spike_rallies['bars_after_spike'].median():.0f}")
            print(f"   Max: {spike_rallies['bars_after_spike'].max()}")
    
    print("\n" + "=" * 80)
    print("✅ Analysis Complete")
    print("=" * 80)

if __name__ == "__main__":
    run_analysis()
