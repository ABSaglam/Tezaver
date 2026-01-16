#!/usr/bin/env python3
"""
HIGH RSI MOMENTUM TEST (backtest_high_rsi.py)
---------------------------------------------
Tests the User Hypothesis: 
"When Daily RSI goes above 65-70, the move often explodes."

Strategy:
- Trigger: Daily RSI crosses above 70.
- No ATR filter.
- Measure: Max Gain in next 5 days.
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def run_high_rsi_monitor():
    print("🚀 TESTING 'HIGH RSI (70+)' HYPOTHESIS...")
    
    # Load DNA
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
    except:
        dna_map = {}

    results = []
    
    processed_count = 0
    
    for idx, symbol in enumerate(DEFAULT_COINS):
        if idx % 50 == 0: print(f"Scanning {idx}/{len(DEFAULT_COINS)}...", end='\r')
        
        # Use 1d directly if available, else 15m resample
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        path_15m = coin_cell_paths.get_history_file(symbol, '15m')
        
        df = None
        
        if path_1d.exists():
            df = pd.read_parquet(path_1d)
        elif path_15m.exists():
            df_15m = pd.read_parquet(path_15m)
            if len(df_15m) > 200:
                df = df_15m.resample('1D', on='datetime').agg({
                    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
                }).dropna()
        
        if df is None: continue
        if df is None: continue
        if len(df) < 50: continue
        
        # Ensure DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
            elif 'timestamp' in df.columns:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.set_index('datetime')
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 0.001)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Detect Crossover > 70
        df['prev_rsi'] = df['rsi'].shift(1)
        mask = (df['rsi'] > 70) & (df['prev_rsi'] <= 70)
        
        # DEBUG
        if symbol == "DASHUSDT":
            print(f"DEBUG DASH: Rows={len(df)}")
            print(f"DEBUG DASH: Index Type={type(df.index)}")
            print(f"DEBUG DASH: Mask Sum={mask.sum()}")
        
        # Identify dates
        if isinstance(df.index, pd.DatetimeIndex):
            sig_dates = df[mask].index
        else:
            sig_dates = df[mask]['datetime']
            
        cluster = dna_map.get(symbol, "UNKNOWN")
        
        for d in sig_dates:
            # Handle timezone
            try:
                ts = pd.Timestamp(d)
                if ts.tz is None: ts = ts.tz_localize('UTC')
                
                target = pd.Timestamp("2024-01-01").tz_localize('UTC')
                if ts < target: continue
                
                # Locate row
                if isinstance(df.index, pd.DatetimeIndex):
                    # Robust loc
                    if d not in df.index: continue
                    loc_idx = df.index.get_loc(d)
                    
                    # Ensure we have future data
                    if loc_idx + 6 > len(df): continue
                    
                    row = df.iloc[loc_idx]
                    future = df.iloc[loc_idx+1 : loc_idx+6]
                else:
                    continue # simplify
                
                entry_price = row['close']
                max_price = future['high'].max()
                max_gain = ((max_price - entry_price) / entry_price) * 100
                
                results.append({
                    'cluster': cluster,
                    'gain': max_gain,
                    'is_win': max_gain > 5,
                    'is_super': max_gain > 20
                })
            except Exception as e:
                # print(e)
                continue
            
    # REPORT
    df_res = pd.DataFrame(results)
    print("\n" + "="*60)
    print("🔥 'HIGH RSI BREAKOUT (>70)' PERFORMANCE (2024-2026)")
    print("="*60)
    print(f"Total Signals: {len(df_res)}")
    print(f"Global Success (>5%): {df_res['is_win'].mean()*100:.1f}%")
    print(f"Global Avg Gain:      {df_res['gain'].mean():.1f}%")
    print("-" * 60)
    
    stats = df_res.groupby('cluster').agg({
        'is_win': 'mean',
        'is_super': 'mean',
        'gain': 'mean',
        'cluster': 'count'
    }).rename(columns={'cluster': 'Signals'})
    
    stats['is_win'] *= 100
    stats['is_super'] *= 100
    stats.columns = ['Success% (>5%)', 'Super% (>20%)', 'Avg Gain%', 'Count']
    stats = stats.sort_values('Avg Gain%', ascending=False)
    
    print(stats.to_string(float_format="%.1f"))

if __name__ == "__main__":
    run_high_rsi_monitor()
