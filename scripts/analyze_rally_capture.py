"""
Rally vs Radar Correlation Analysis
===================================
Analyzes how many historical rallies were preceded by GEN-RADAR signals.
Output: Hit Rate by Category and DNA Tier.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from tezaver.core import coin_cell_paths
from tezaver.mining.rally_miner import mine_rallies

def run_correlation_analysis():
    print("=== 📊 GEN-RADAR vs RALLY CORRELATION ANALYSIS ===")
    
    coin_cells_dir = Path("/Users/alisaglam/TezaverMac/coin_cells")
    coins = [d.name for d in coin_cells_dir.iterdir() if d.is_dir()]
    
    rally_events = []
    
    for idx, symbol in enumerate(coins):
        if idx % 50 == 0:
            print(f"Mining Rallies: {idx}/{len(coins)} {symbol}...")
            
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, "1d")
            if not path_1d.exists(): continue
            
            df_1d = pd.read_parquet(path_1d)
            if 'radar_category' not in df_1d.columns: continue
            
            # Detect rallies (at least 10% gain in max 10 days)
            rallies = mine_rallies(df_1d, symbol, max_window=10, min_gain=0.10)
            
            # GET DNA TIER
            with open('library/coin_dna_definitive.json', 'r') as f:
                dna_map = {p['symbol']: p['tier'] for p in json.load(f)}
            tier = dna_map.get(symbol, 'N/A')

            for r in rallies:
                # FILTER: Skip listing artifacts (massive first day jumps)
                if r['gain'] > 400: continue
                if r['start_idx'] < 20: continue # Need warmup
                
                start_idx = r['start_idx']
                # Look back at GEN-RADAR status 0-2 days before the rally start
                # or on the very day it started
                lookback_range = df_1d.iloc[max(0, start_idx - 2) : start_idx + 1]
                
                # Did we have a signal?
                signals = lookback_range[lookback_range['radar_category'] != 'NONE']
                
                has_signal = not signals.empty
                best_signal = "NONE"
                best_score = 0
                
                if has_signal:
                    # Pick the highest priority signal (TREND > NINJA > BREAKOUT > WATCH)
                    priority = {'TREND': 3, 'NINJA': 2, 'BREAKOUT': 1, 'WATCH': 0, 'NONE': -1}
                    top_row = signals.sort_values(by=['radar_category'], key=lambda x: x.map(priority), ascending=False).iloc[0]
                    best_signal = top_row['radar_category']
                    best_score = top_row['radar_score']

                rally_events.append({
                    'symbol': symbol,
                    'start_time': r['start_time'],
                    'gain': r['gain'],
                    'has_signal': has_signal,
                    'radar_category': best_signal,
                    'radar_score': best_score,
                    'tier': r['gain'] # Temporary for grouping
                })
        except Exception:
            continue

    if not rally_events:
        print("No rallies or signals found to correlate.")
        return

    df = pd.DataFrame(rally_events)
    
    # Classify rally tiers
    def get_rally_tier(gain):
        if gain >= 30: return '🥈 DIAMOND (>30%)'
        if gain >= 20: return '🥇 GOLD (20-30%)'
        return '🥉 SILVER (10-20%)'
    
    df['rally_tier'] = df['gain'].apply(get_rally_tier)
    
    print("\n" + "="*50)
    print("📈 RADAR CAPTURE PERFORMANCE (Hit Rates)")
    print("="*50)
    
    # 📊 Hit Rate by Rally Tier
    pivot = df.groupby('rally_tier')['has_signal'].agg(['count', 'mean'])
    pivot.columns = ['Total Rallies', 'Capture Rate (Hit %)']
    pivot['Capture Rate (Hit %)'] = (pivot['Capture Rate (Hit %)'] * 100).round(1).astype(str) + '%'
    print("\n[HIT RATE BY RALLY SIZE]")
    print(pivot.to_string())
    
    # 🗂️ Category Breakdown (Which category caught which rallies?)
    print("\n[WHICH CATEGORY CAUGHT THE RALLIES?]")
    cat_dist = df[df['has_signal']].groupby(['rally_tier', 'radar_category']).size().unstack(fill_value=0)
    print(cat_dist.to_string())
    
    # 🔍 Miss Analysis
    print("\n" + "="*50)
    print("🚩 MISS ANALYSIS (Why did we miss?)")
    print("="*50)
    misses = df[~df['has_signal']]
    print(f"Total Missed Rallies: {len(misses)}")
    if not misses.empty:
        print("\nTop 5 Large Missed Rallies (Need improvement):")
        print(misses.sort_values('gain', ascending=False).head(5)[['symbol', 'start_time', 'gain']].to_string(index=False))

if __name__ == "__main__":
    run_correlation_analysis()
