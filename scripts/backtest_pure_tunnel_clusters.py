#!/usr/bin/env python3
"""
PURE TUNNEL BACKTEST BY CLUSTER (backtest_pure_tunnel_clusters.py)
------------------------------------------------------------------
Measures the reliability of the Ayaş Tüneli signal ITSELF (Permission).
No Sniper execution, just "Did it go up?"

Metrics:
- Success Rate: Max Gain > 5% within 5 days.
- Diamond Rate: Max Gain > 20% within 5 days.
- Grouped by Coin DNA Cluster (ROCKET vs Rest).

Data Source: 15m.parquet (Resampled to 1D for Signal, Used raw for Max Gain check)
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

def run_pure_backtest():
    print("🚇 BACKTESTING PURE TUNNEL STRENGTH (By Cluster)...")
    
    # Load DNA
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
    except:
        print("⚠️ Warning: DNA map not found. Proceeding without clusters.")
        dna_map = {}

    results = []
    
    processed_count = 0
    
    for idx, symbol in enumerate(DEFAULT_COINS):
        if idx % 50 == 0: print(f"Scanning {idx}/{len(DEFAULT_COINS)}...", end='\r')
        
        # Source of Truth: 15m
        path_15m = coin_cell_paths.get_history_file(symbol, '15m')
        if not path_15m.exists(): continue
        
        try:
            df_15m = pd.read_parquet(path_15m)
            if len(df_15m) < 500: continue
            
            # Resample for Daily Signal
            # We need Daily Close for ATR/RSI calculation
            df_daily = df_15m.resample('1D', on='datetime').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            if len(df_daily) < 50: continue
            
            # Indicators
            df_daily['atr_val'] = (df_daily['high'] - df_daily['low']).rolling(14).mean()
            df_daily['atr_pct'] = (df_daily['atr_val'] / df_daily['close']) * 100
            
            delta = df_daily['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 0.001)
            df_daily['rsi'] = 100 - (100 / (1 + rs))
            
            # Detect Signals
            mask = (
                ((df_daily['atr_pct'] > 15) & (df_daily['rsi'] > 55) & (df_daily['rsi'] < 70)) | # TREND
                ((df_daily['atr_pct'] > 12) & (df_daily['atr_pct'] <= 15) & (df_daily['rsi'] > 60) & (df_daily['rsi'] < 75)) # NINJA
            )
            
            # Only check signals since 2024 for speed/relevance
            sig_indices = df_daily[mask].index
            sig_dates = [d for d in sig_indices if d >= pd.Timestamp("2024-01-01").tz_localize('UTC')]
            
            cluster = dna_map.get(symbol, "UNKNOWN")
            
            for signal_date in sig_dates:
                # Max Gain Verification using 15m resolution
                # Window: 5 Days (120 hours) starting from signal day close
                # Signal calculated on daily close (00:00 UTC usually)
                
                start_time = signal_date
                end_time = signal_date + pd.Timedelta(days=5)
                
                # Check 15m price action in window
                window_data = df_15m[(df_15m['datetime'] > start_time) & (df_15m['datetime'] <= end_time)]
                
                if window_data.empty: continue
                
                entry_price = df_daily.loc[signal_date, 'close']
                max_price = window_data['high'].max()
                
                max_gain_pct = ((max_price - entry_price) / entry_price) * 100
                
                results.append({
                    'cluster': cluster,
                    'is_success': max_gain_pct >= 5.0, # Success threshold >5%
                    'is_diamond': max_gain_pct >= 20.0,
                    'max_gain': max_gain_pct
                })
                
            processed_count += 1
            
        except Exception:
            continue

    # REPORTING
    df_res = pd.DataFrame(results)
    
    print("\n" + "="*60)
    print("🚇 PURE TUNNEL RELIABILITY REPORT (2024-2026)")
    print("="*60)
    print(f"Total Signals: {len(df_res)}")
    print(f"Overall Success Rate (>5%): {df_res['is_success'].mean()*100:.1f}%")
    print(f"Overall Avg Max Gain:     {df_res['max_gain'].mean():.1f}%")
    print("-" * 60)
    
    # Cluster Breakdown
    stats = df_res.groupby('cluster').agg({
        'is_success': 'mean',
        'is_diamond': 'mean',
        'max_gain': 'mean',
        'cluster': 'count'
    }).rename(columns={'cluster': 'Signals'})
    
    stats['is_success'] = stats['is_success'] * 100
    stats['is_diamond'] = stats['is_diamond'] * 100
    
    stats.columns = ['Success% (>5%)', 'Diamond% (>20%)', 'Avg Max Gain%', 'Signal Count']
    stats = stats.sort_values('Success% (>5%)', ascending=False)
    
    print(stats.to_string(float_format="%.1f"))
    print("-" * 60)
    
    # Save
    df_res.to_csv('library/rally_dna/pure_tunnel_results.csv', index=False)
    print("📁 Saved detailed results to library/rally_dna/pure_tunnel_results.csv")

if __name__ == "__main__":
    run_pure_backtest()
