#!/usr/bin/env python3
"""
Active Sniper List Generator
----------------------------
Scans daily data for the last 4 days to identify "Active" monitoring targets.
Annotates each target with:
- Signal Date
- Day Count (Day 1, 2, 3, 4)
- Signal Type (TREND/NINJA)
- Coin DNA Cluster (ROCKET, ACTIVE, etc.)
"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def calculate_atr(high, low, close, period=14):
    high_low = high - low
    high_close = (high - close.shift()).abs()
    low_close = (low - close.shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def main():
    print("🔍 GENERATING ACTIVE SNIPER LIST...")
    print("=" * 60)
    
    # Load DNA
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        # Map symbol -> "emoji cluster_name" (e.g., "🚀 ROCKET")
        dna['full_cluster'] = dna['emoji'] + " " + dna['cluster_name']
        dna_map = dict(zip(dna['symbol'], dna['full_cluster']))
    except:
        dna_map = {}

    # Define Monitoring Window (Yesterday's close is "Day 1" usually, 
    # but based on user prompt "today's tunnel" implies today's data availability.
    # We will look at the last 5 available dates in the dataset regardless of real time to be safe.
    # But usually we align to the latest date found.
    
    active_targets = []
    latest_global_date = None
    
    # First pass: find latest date
    for symbol in DEFAULT_COINS[:50]: # Sample 50 to find latest date quickly
        path = coin_cell_paths.get_history_file(symbol, '1d')
        if path.exists():
            df = pd.read_parquet(path)
            if not df.empty:
                last_dt = df['datetime'].max()
                if latest_global_date is None or last_dt > latest_global_date:
                    latest_global_date = last_dt
    
    if latest_global_date is None:
        print("❌ No data found.")
        return

    print(f"📅 Latest Data Date: {latest_global_date.date()}")
    
    # Calculate target dates: Day 1 (Latest) to Day 5
    target_dates = [latest_global_date - timedelta(days=i) for i in range(5)]
    
    print("\nScanning for signals on:")
    for i, d in enumerate(target_dates):
        print(f"  Day {i+1}: {d.date()}")
    print("-" * 60)

    # Scan All Coins
    for symbol in DEFAULT_COINS:
        path = coin_cell_paths.get_history_file(symbol, '1d')
        if not path.exists(): continue
        
        try:
            df = pd.read_parquet(path)
            if len(df) < 50: continue
            
            # Indicators
            df['atr'] = calculate_atr(df['high'], df['low'], df['close'])
            df['atr_pct'] = (df['atr'] / df['close']) * 100
            df['rsi'] = calculate_rsi(df['close'])
            
            # Check last 5 days
            # Create a localized window for easier checking
            # We check if a signal happened on ANY of the target dates
            # IMPORTANT: A separate signal logic applied per date row
            
            relevant_rows = df[df['datetime'].isin(target_dates)].copy()
            
            for _, row in relevant_rows.iterrows():
                dt = row['datetime']
                
                # Determine "Day X"
                days_ago = (latest_global_date - dt).days
                day_num = days_ago + 1 # 0 days ago = Day 1
                
                if day_num > 5: continue # Should not happen due to filter
                
                # Check Signal
                is_trend = (row['atr_pct'] > 15) and (55 < row['rsi'] < 70)
                is_ninja = (12 < row['atr_pct'] <= 15) and (60 < row['rsi'] < 75)
                
                if is_trend or is_ninja:
                    sig_type = "TREND" if is_trend else "NINJA"
                    cluster = dna_map.get(symbol, "UNKNOWN")
                    
                    active_targets.append({
                        'symbol': symbol,
                        'day': day_num,
                        'signal_date': dt.date(),
                        'type': sig_type,
                        'cluster': cluster,
                        'cluster_clean': cluster.split(' ')[1] if ' ' in cluster else cluster, # Remove emoji for sorting
                        'rsi': row['rsi'],
                        'atr_pct': row['atr_pct']
                    })
                    
        except Exception:
            continue

    if not active_targets:
        print("❌ No active targets found in the last 5 days.")
        return

    # Convert to DataFrame
    df_res = pd.DataFrame(active_targets)
    
    # Sort for report: Day (1->5), then Cluster Priority
    cluster_priority = {'ROCKET': 0, 'ACTIVE': 1, 'CALM': 2, 'NEEDLE': 3, 'STABLE': 4, 'UNKNOWN': 9}
    df_res['prio'] = df_res['cluster_clean'].map(lambda x: cluster_priority.get(x, 99))
    
    df_res = df_res.sort_values(['day', 'prio', 'symbol'])
    
    # Display Report
    print(f"\n🎯 ACTIVE TUNNEL SIGNALS ({len(df_res)} Candidates)")
    
    for day in range(1, 6):
        day_targets = df_res[df_res['day'] == day]
        if day_targets.empty:
            continue
            
        date_str = day_targets.iloc[0]['signal_date']
        print(f"\n📅 DAY {day} (Signal: {date_str}) - {len(day_targets)} Coins")
        print("-" * 80)
        print(f"{'SYMBOL':<15} {'CLUSTER':<15} {'TYPE':<10} {'RSI':<6} {'ATR%':<6}")
        print("-" * 80)
        
        for _, row in day_targets.iterrows():
            print(f"{row['symbol']:<15} {row['cluster']:<15} {row['type']:<10} {row['rsi']:.1f}   {row['atr_pct']:.1f}")
            
    # Save CSV
    df_res.to_csv('library/active_tunnel_signals.csv', index=False)
    print(f"\n📁 Saved list to library/active_tunnel_signals.csv")

if __name__ == "__main__":
    main()
