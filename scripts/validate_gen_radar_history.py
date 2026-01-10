"""
GEN-RADAR Backtest Validator v2
===============================
Analyzes historical accuracy of TREND and NINJA signals.
Cross-references signals with DNA tiers to find 'Golden Segments'.
"""

import pandas as pd
import numpy as np
import json
import time
from pathlib import Path
from tezaver.core import config, coin_cell_paths
from tezaver.mining.daily_radar_engine import DailyRadarEngine

def run_gen_radar_backtest():
    print("=== 🧬 GEN-RADAR HISTORICAL VALIDATOR v2 ===")
    
    engine = DailyRadarEngine()
    coins = config.DEFAULT_COINS
    
    results_records = []
    
    # Load DNA profiles once
    with open('library/coin_dna_definitive.json', 'r') as f:
        dna_profiles = {p['symbol']: p for p in json.load(f)}
    
    total_coins = len(coins)
    
    for c_idx, symbol in enumerate(coins):
        if c_idx % 20 == 0:
            print(f"Processing: {c_idx}/{total_coins} {symbol}...")
            
        dna = dna_profiles.get(symbol)
        if not dna: continue
        
        # Load data
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, "1d")
            path_4h = coin_cell_paths.get_history_file(symbol, "4h")
            if not path_1d.exists() or not path_4h.exists(): continue
            
            df_1d = pd.read_parquet(path_1d)
            df_4h = pd.read_parquet(path_4h)
            
            if len(df_1d) < 50 or len(df_4h) < 100: continue
            
            # Standardize dates
            df_1d['dt'] = pd.to_datetime(df_1d['datetime'], utc=True)
            df_4h['dt'] = pd.to_datetime(df_4h['datetime'], utc=True)
            
            # Iterate through days (last 1 year if possible)
            # Skip first 30 days for indicator warmup
            start_idx = max(30, len(df_1d) - 365) 
            
            for i in range(start_idx, len(df_1d) - 10):
                target_dt = df_1d.iloc[i]['dt']
                
                # 1. Simulate data availability at that moment
                d_slice = df_1d.iloc[:i+1]
                h_slice = df_4h[df_4h['dt'] <= target_dt]
                
                if len(h_slice) < 20: continue
                
                # 2. Daily & Momentum Metrics
                daily = engine.calculate_daily_structure(d_slice)
                momentum = engine.calculate_4h_momentum(h_slice)
                
                if not daily or not momentum: continue
                daily.symbol = symbol
                
                # 3. Categorize
                is_ninja = engine.is_ninja_candidate(daily, momentum, dna)
                is_trend = False
                
                # Even if not ninja, check if it passes trend filters
                if not is_ninja:
                    if engine.passes_daily_filter(daily, dna) and engine.passes_momentum_filter(momentum, dna):
                        category = engine.categorize(daily, momentum, dna)
                        if category == "TREND":
                             is_trend = True
                        else:
                             # We skip WATCH for this backtest to focus on high-conviction
                             continue
                    else:
                        continue
                else:
                    category = "NINJA"

                # 4. TRACK PERFORMANCE (Next 10 days)
                entry_price = d_slice['close'].iloc[-1]
                future = df_1d.iloc[i+1 : i+11]
                
                max_high = future['high'].max()
                max_gain = (max_high / entry_price - 1) * 100
                
                results_records.append({
                    'symbol': symbol,
                    'date': target_dt.date(),
                    'tier': dna['tier'],
                    'category': category,
                    'score': engine.calculate_score(daily, momentum),
                    'max_gain': max_gain
                })
                
        except Exception:
            continue

    if not results_records:
        print("No signals found in history.")
        return

    report_df = pd.DataFrame(results_records)
    
    print("\n" + "="*40)
    print("📈 GEN-RADAR STATISTICAL PERFORMANCE")
    print("="*40)
    
    # 1. Performance by Category
    cat_stats = report_df.groupby('category')['max_gain'].agg(['count', 'mean', 'median', lambda x: (x >= 10).mean()*100])
    cat_stats.columns = ['Signal Count', 'Avg Max Gain %', 'Median Gain %', 'Hit Rate (+10%)']
    print("\n[PERFORMANCE BY CATEGORY]")
    print(cat_stats.to_string())
    
    # 2. Ninja Explosiveness Check
    ninja_hits = report_df[report_df['category'] == 'NINJA']
    if not ninja_hits.empty:
        wick_rate = (ninja_hits['max_gain'] >= 20).mean() * 100
        print(f"\n🚀 NINJA EXPLOSIVENESS (+20% in 10 days): {wick_rate:.1f}%")
    
    # 3. Trend Reliability by DNA Tier
    trend_hits = report_df[report_df['category'] == 'TREND']
    if not trend_hits.empty:
        tier_stats = trend_hits.groupby('tier')['max_gain'].agg(['count', 'mean', lambda x: (x >= 5).mean()*100])
        tier_stats.columns = ['Count', 'Avg Gain %', 'Hit Rate (+5%)']
        print("\n[TREND RELIABILITY BY DNA TIER]")
        print(tier_stats.to_string())

    # 4. Save results
    report_df.to_csv('analysis/gen_radar_historical_signals.csv', index=False)
    print(f"\nDetailed signals saved to analysis/gen_radar_historical_signals.csv")

if __name__ == "__main__":
    run_gen_radar_backtest()
