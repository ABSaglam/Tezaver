#!/usr/bin/env python3
"""
Signal Trajectory Analysis (The 'Approach Vector' Study)
--------------------------------------------------------
Investigates the hypothesis: "Does the path TO the tunnel determine the outcome?"

Methodology:
1. Load all historic signals.
2. Link them to their outcomes (Tier: Diamond vs Coal).
3. For each signal, extract the "Pre-Signal Context" (Last 3-5 days):
    - RSI Momentum (Delta RSI)
    - Price Trend (Slope)
    - ATR Trend (Volatility Expansion/Contraction)
4. Compare 'Winners' vs 'Losers' to find distinctive patterns.
"""

import pandas as pd
import numpy as np
import sys
import os
from scipy.stats import linregress

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths

def get_slope(series):
    """Calculates linear slope of a series."""
    if len(series) < 2: return 0
    x = np.arange(len(series))
    slope, _, _, _, _ = linregress(x, series)
    return slope

def analyze_trajectories():
    print("🕵️ Analyzing Signal Trajectories...")
    
    # 1. Load Signals & Outcomes (from a Backtest Report or re-generate simplified)
    # We will use the 'ayas_tuneli_2y_120h_rapor.md' parsing logic or simpler:
    # Scan raw files again to find signals, then check T+5 outcome.
    
    # Let's load the coin list
    from tezaver.core.config import DEFAULT_COINS
    
    results = []
    
    # Limit to 50 random coins for speed in this initial study, or full scan?
    # Full scan is better for statistics.
    
    scan_count = 0
    for symbol in DEFAULT_COINS:
        path = coin_cell_paths.get_history_file(symbol, '1d')
        if not path.exists(): continue
        
        try:
            df = pd.read_parquet(path)
            if len(df) < 30: continue
            
            # Indicators
            df['atr_val'] = (df['high'] - df['low']).rolling(14).mean()
            df['atr_pct'] = (df['atr_val'] / df['close']) * 100
            
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 0.001)
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Identify Signals
            # TREND: ATR > 15, 55 < RSI < 70
            # NINJA: ATR 12-15, 60 < RSI < 75
            
            mask = (
                ((df['atr_pct'] > 15) & (df['rsi'] > 55) & (df['rsi'] < 70)) |
                ((df['atr_pct'] > 12) & (df['atr_pct'] <= 15) & (df['rsi'] > 60) & (df['rsi'] < 75))
            )
            
            signal_idxs = df.index[mask].tolist()
            
            for idx in signal_idxs:
                if idx < 5 or idx > len(df) - 6: continue # Need context and outcome
                
                row = df.loc[idx]
                
                # --- OUTCOME (Success or Failure?) ---
                # Check next 5 days
                future = df.loc[idx+1 : idx+5]
                max_gain = ((future['high'].max() - row['close']) / row['close']) * 100
                
                # Classification
                if max_gain >= 20: outcome = "DIAMOND"
                elif max_gain >= 10: outcome = "GOLD"
                elif max_gain >= 5: outcome = "SILVER"
                elif max_gain < 0: outcome = "COAL_LOSS" # Simplified
                else: outcome = "STAGNANT"
                
                if outcome == "STAGNANT": continue # Ignore noise
                
                # --- PRE-SIGNAL CONTEXT (The "Development Process") ---
                pre_window = df.loc[idx-3 : idx] # Last 4 bars (Day -3 to Signal Day)
                
                # 1. RSI Trajectory (How fast did it heat up?)
                rsi_start = pre_window.iloc[0]['rsi']
                rsi_end = pre_window.iloc[-1]['rsi']
                rsi_delta = rsi_end - rsi_start
                rsi_slope = get_slope(pre_window['rsi'])
                
                # 2. Price Action (V-Shape or Grind?)
                # Price change in last 3 days
                price_gain_3d = ((pre_window.iloc[-1]['close'] - pre_window.iloc[0]['close']) / pre_window.iloc[0]['close']) * 100
                
                # 3. ATR Trend (Is Volatility expanding?)
                atr_slope = get_slope(pre_window['atr_pct'])
                
                results.append({
                    'outcome': outcome,
                    'type': "WINNER" if max_gain >= 10 else "LOSER", # Binary for simpler stats
                    'rsi_delta_3d': rsi_delta,
                    'rsi_slope': rsi_slope,
                    'price_gain_3d': price_gain_3d,
                    'atr_slope': atr_slope,
                    'signal_rsi': row['rsi'],
                    'signal_atr': row['atr_pct']
                })
                
            scan_count += 1
            if scan_count % 50 == 0: print(f"Scanned {scan_count} coins...", end='\r')
            
        except: continue

    # ANALYSIS
    res_df = pd.DataFrame(results)
    
    print("\n" + "="*60)
    print("📐 TRAJECTORY ANALYSIS RESULTS")
    print("="*60)
    print(f"Total Signals Analyzed: {len(res_df)}")
    
    # Pivot Table
    print("\nMEAN VALUES by Outcome Group:")
    pivot = res_df.groupby('type')[['rsi_delta_3d', 'rsi_slope', 'price_gain_3d', 'atr_slope']].mean()
    print(pivot)
    
    # Detailed for Diamond
    print("\nDetailed breakdown:")
    pivot_det = res_df.groupby('outcome')[['rsi_delta_3d', 'rsi_slope']].mean().sort_values('rsi_slope', ascending=False)
    print(pivot_det)
    
    # Hypothesis Check
    # Does High RSI Velocity lead to Diamonds?
    winners = res_df[res_df['type'] == 'WINNER']
    losers = res_df[res_df['type'] == 'LOSER']
    
    print("\n🔍 HYPOTHESIS CHECK:")
    print(f"Avg RSI Slope (Winners): {winners['rsi_slope'].mean():.2f}")
    print(f"Avg RSI Slope (Losers):  {losers['rsi_slope'].mean():.2f}")
    
    # Save
    res_df.to_csv('library/rally_dna/trajectory_analysis.csv', index=False)

if __name__ == "__main__":
    analyze_trajectories()
