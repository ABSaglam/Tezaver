#!/usr/bin/env python3
"""
WEEKLY TREND HYPOTHESIS VERIFICATION (verify_high_rsi_weekly_context.py)
------------------------------------------------------------------------
Tests User Hypothesis:
"Daily RSI > 70 is OVERBOUGHT (Sell) if Weekly is Weak (<55).
 Daily RSI > 70 is MOMENTUM (Buy) if Weekly is Strong (>=55)."

Methodology:
1. Find all "Daily RSI Cross > 70" events.
2. Check Weekly RSI at that moment.
3. Compare 5-day Forward Returns for:
   - Weekly < 50 (Bear/Range)
   - Weekly 50-60 (Early Trend)
   - Weekly > 60 (Established Trend)
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

def run_hypothesis_test():
    print("🧪 TESTING: DAILY RSI > 70 vs WEEKLY TREND...")
    
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
    except:
        dna_map = {}

    results = []
    
    for idx, symbol in enumerate(DEFAULT_COINS):
        if idx % 50 == 0: print(f"Scanning {idx}/{len(DEFAULT_COINS)}...", end='\r')
        
        # 1. Load Data (Using 1d / 15m)
        path = coin_cell_paths.get_history_file(symbol, '15m') # Using 15m as base for robust sync
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

            # 2. Daily & Weekly Resample
            df_weekly = df_15m.resample('W-MON').agg({'close': 'last'}).dropna()
            df_weekly['rsi_w'] = calculate_rsi(df_weekly['close'])
            
            df_daily = df_15m.resample('1D').agg({'close': 'last', 'high': 'max'}).dropna()
            df_daily['rsi_d'] = calculate_rsi(df_daily['close'])
            
            if len(df_weekly) < 20 or len(df_daily) < 50: continue
            
            # 3. Detect Trigger: Daily RSI Cross > 70
            df_daily['prev_rsi'] = df_daily['rsi_d'].shift(1)
            # Trigger: Cross > 70
            mask = (df_daily['rsi_d'] > 70) & (df_daily['prev_rsi'] <= 70)
            
            sig_indices = df_daily[mask].index
            # Filter 2024+
            sig_dates = [d for d in sig_indices if d >= pd.Timestamp("2024-01-01").tz_localize('UTC')]
            
            cluster = dna_map.get(symbol, "UNKNOWN")
            
            for d in sig_dates:
                # 4. Get Context: Weekly RSI (Previous closed week)
                prior_weeks = df_weekly[:d]
                if len(prior_weeks) < 1: continue
                
                weekly_rsi = prior_weeks.iloc[-1]['rsi_w']
                if np.isnan(weekly_rsi): continue
                
                # 5. Measure Outcome (Next 5 Days)
                loc_idx = df_daily.index.get_loc(d)
                if loc_idx + 6 > len(df_daily): continue
                
                entry_price = df_daily.iloc[loc_idx]['close']
                future = df_daily.iloc[loc_idx+1 : loc_idx+6]
                max_price = future['high'].max()
                
                max_gain = ((max_price - entry_price) / entry_price) * 100
                
                results.append({
                    'cluster': cluster,
                    'weekly_rsi': weekly_rsi,
                    'gain': max_gain,
                    'is_success': max_gain > 5,
                    'is_super': max_gain > 20
                })

        except Exception: continue

    # REPORT
    df_res = pd.DataFrame(results)
    print("\n" + "="*60)
    print("🧪 WEEKLY TREND IMPACT ON 'RSI > 70' SIGNALS")
    print("="*60)
    print(f"Total 'Daily RSI > 70' Signals: {len(df_res)}")
    
    # Categorize Weekly RSI
    def categorize(rsi):
        if rsi < 50: return "1. < 50 (NO Trend)"
        if rsi < 60: return "2. 50-60 (START)"
        if rsi < 80: return "3. 60-80 (STRONG)"
        return "4. > 80 (EXTREME)"
        
    df_res['trend_zone'] = df_res['weekly_rsi'].apply(categorize)
    
    # Global Stats
    print("\n🌍 ALL COINS (Global Impact):")
    stats = df_res.groupby('trend_zone').agg({
        'is_success': 'mean',
        'is_super': 'mean',
        'gain': 'mean',
        'cluster': 'count'
    })
    stats['is_success'] *= 100
    stats['is_super'] *= 100
    stats.columns = ['Success% (>5%)', 'Super% (>20%)', 'Avg Gain%', 'Count']
    print(stats.to_string(float_format="%.1f"))
    
    # Cluster Breakdown (ROCKET vs ACTIVE)
    for c_name in ['ROCKET', 'ACTIVE']:
        print(f"\n👉 {c_name} CLUSTER:")
        sub = df_res[df_res['cluster'] == c_name]
        if sub.empty: continue
        s = sub.groupby('trend_zone').agg({
            'is_success': 'mean', 
            'gain': 'mean', 
            'cluster': 'count'
        })
        s['is_success'] *= 100
        s.columns = ['Success%', 'Avg Gain%', 'Count']
        print(s.to_string(float_format="%.1f"))

if __name__ == "__main__":
    run_hypothesis_test()
