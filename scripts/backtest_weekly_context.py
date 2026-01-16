#!/usr/bin/env python3
"""
WEEKLY CONTEXT BACKTEST (backtest_weekly_context.py)
----------------------------------------------------
Analyzes the impact of WEEKLY RSI on the performance of DAILY TUNNEL SIGNALS.

Hypothesis: "Daily signals work better when Weekly RSI is in a specific zone (e.g., Rising, >50)."

Methodology:
1. Resample 15m to WEEKLY -> Calculate Weekly RSI.
2. Resample 15m to DAILY -> Identify "Ayaş Tüneli" Signals.
3. Match each Daily Signal with the Weekly RSI of the *previous completed week*.
4. Analyze Success Rate (>5% gain) bucketed by Weekly RSI zones.
"""

import pandas as pd
import numpy as np
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def run_weekly_context_analysis():
    print("📅 ANALYZING WEEKLY RSI CONTEXT ON DAILY SIGNALS...")
    
    # Load DNA
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
    except:
        dna_map = {}

    results = []
    
    for idx, symbol in enumerate(DEFAULT_COINS):
        if idx % 50 == 0: print(f"Scanning {idx}/{len(DEFAULT_COINS)}...", end='\r')
        
        path = coin_cell_paths.get_history_file(symbol, '15m')
        if not path.exists(): continue
        
        try:
            df_15m = pd.read_parquet(path)
            if len(df_15m) < 2000: continue
            
            # Ensure DatetimeIndex
            if not isinstance(df_15m.index, pd.DatetimeIndex):
                if 'datetime' in df_15m.columns:
                    df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
                    df_15m = df_15m.set_index('datetime')
                elif 'timestamp' in df_15m.columns:
                    df_15m['datetime'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
                    df_15m = df_15m.set_index('datetime')

            # 1. WEEKLY DATA
            # Resample to Weekly (W-MON)
            df_weekly = df_15m.resample('W-MON').agg({
                'close': 'last'
            }).dropna()
            
            if len(df_weekly) < 15: continue
            
            df_weekly['rsi_weekly'] = calculate_rsi(df_weekly['close'])
            
            # 2. DAILY DATA (Signals)
            df_daily = df_15m.resample('1D').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
            }).dropna()
            
            if len(df_daily) < 50: continue
            
            df_daily['atr_val'] = (df_daily['high'] - df_daily['low']).rolling(14).mean()
            df_daily['atr_pct'] = (df_daily['atr_val'] / df_daily['close']) * 100
            df_daily['rsi_daily'] = calculate_rsi(df_daily['close'])
            
            # 3. DETECT DAILY SIGNALS
            mask = (
                ((df_daily['atr_pct'] > 15) & (df_daily['rsi_daily'] > 55) & (df_daily['rsi_daily'] < 70)) | 
                ((df_daily['atr_pct'] > 12) & (df_daily['atr_pct'] <= 15) & (df_daily['rsi_daily'] > 60) & (df_daily['rsi_daily'] < 75))
            )
            
            sig_indices = df_daily[mask].index
            # Filter 2024+
            sig_dates = [d for d in sig_indices if d >= pd.Timestamp("2024-01-01").tz_localize('UTC')]
            
            cluster = dna_map.get(symbol, "UNKNOWN")
            
            # 4. MATCH & MEASURE
            for signal_date in sig_dates:
                # Find the latest WEEKLY close *before* this signal
                # Since 'W-MON' labels with the end of the week, we look for dates <= signal_date
                # Actually, best is to use 'asof'
                
                # Check outcome first
                start_time = signal_date
                end_time = signal_date + pd.Timedelta(days=5)
                
                # Check 5-day max gain from 15m
                # Optimized: slicing 15m is slow, let's approximation with Daily high
                future_daily = df_daily.loc[start_time + pd.Timedelta(days=1) : end_time]
                if len(future_daily) < 1: continue
                
                entry_price = df_daily.loc[signal_date, 'close']
                max_price = future_daily['high'].max()
                max_gain = ((max_price - entry_price) / entry_price) * 100
                
                # Get Weekly Context
                # Using searchsorted or asof
                # Index must be sorted
                # weekly_shapshot = df_weekly.loc[:signal_date].iloc[-1] # Simplest
                
                prior_weeks = df_weekly[:signal_date]
                if len(prior_weeks) < 1: continue
                
                weekly_rsi = prior_weeks.iloc[-1]['rsi_weekly']
                if np.isnan(weekly_rsi): continue
                
                results.append({
                    'cluster': cluster,
                    'weekly_rsi': weekly_rsi,
                    'is_success': max_gain > 5,
                    'is_super': max_gain > 20,
                    'gain': max_gain
                })
                
        except Exception as e:
            continue

    # REPORTING
    df_res = pd.DataFrame(results)
    
    print("\n" + "="*60)
    print("📅 WEEKLY RSI IMPACT REPORT (2024-2026)")
    print("="*60)
    print(f"Total Signals: {len(df_res)}")
    
    # Binning Weekly RSI
    bins = [0, 40, 50, 60, 70, 80, 100]
    labels = ['<40 (Bear)', '40-50 (Weak)', '50-60 (Bull Start)', '60-70 (Strong)', '70-80 (Overbought)', '>80 (Extreme)']
    
    df_res['w_zone'] = pd.cut(df_res['weekly_rsi'], bins=bins, labels=labels)
    
    # Group by Zone
    stats = df_res.groupby('w_zone').agg({
        'is_success': 'mean',
        'is_super': 'mean',
        'gain': 'mean',
        'cluster': 'count'
    }).rename(columns={'cluster': 'Signals'})
    
    stats['is_success'] *= 100
    stats['is_super'] *= 100
    stats.columns = ['Success% (>5%)', 'Super% (>20%)', 'Avg Gain%', 'Count']
    
    print(stats.to_string(float_format="%.1f"))
    print("-" * 60)
    
    # ROCKET Specific
    print("\n🚀 ROCKET CLUSTER ONLY:")
    rocket_df = df_res[df_res['cluster'] == 'ROCKET']
    if not rocket_df.empty:
        r_stats = rocket_df.groupby('w_zone').agg({
            'is_success': 'mean',
            'is_super': 'mean',
            'gain': 'mean',
            'cluster': 'count'
        })
        r_stats['is_success'] *= 100
        r_stats['is_super'] *= 100
        r_stats.columns = ['Success%', 'Super%', 'Avg Gain', 'Count']
        print(r_stats.to_string(float_format="%.1f"))
        
if __name__ == "__main__":
    run_weekly_context_analysis()
