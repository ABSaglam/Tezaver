#!/usr/bin/env python3
"""
TEZAVER PARADOX OPTIMIZER
Brute-force optimization to find the "Holy Grail" filter settings.

Scoring Logic:
- Diamond/Gold Retention is Critical (Weighted x3)
- Garbage Reduction is Important (Weighted x1)
- Win Rate must be Maximized
"""

import json
import itertools

def parse_desc(desc):
    # Example: "R=0.7%, V=5.4x" or "Drop=-4.2%, V=0.5x"
    try:
        parts = desc.split(',')
        p_val = float(parts[0].split('=')[1].replace('%',''))
        v_val = float(parts[1].split('=')[1].replace('x',''))
        # For Silent Scream, p_val is Range (always positive). 
        # For Feather Fall, p_val is Drop (negative).
        return abs(p_val), v_val
    except:
        return 0.0, 0.0

def run_optimizer():
    try:
        with open("temp_paradox_raw.json", "r") as f:
            raw_events = json.load(f)
    except FileNotFoundError:
        print("Run scanner first!")
        return

    print(f"Loaded {len(raw_events)} raw events.")
    
    # Initial Stats
    total_diamonds = sum(1 for e in raw_events if e['outcome_24h'] >= 20.0) # Gold+Diamond as "Gems"
    total_garbage = sum(1 for e in raw_events if e['outcome_24h'] < 5.0)
    print(f"Target Gems (Gain > 20%): {total_diamonds}")
    
    # PARAMETER GRID (Expanded for Sniper Mode + Dimensions)
    grid_price = [0.3, 0.5, 0.8, 1.0, 1.2, 1.5]
    grid_vol   = [3.0, 5.0, 7.0, 10.0, 15.0]
    grid_rsi   = [40, 50, 60, 100] # RSI must be BELOW this (Dip Check)
    grid_rib   = ["ANY", "BULL", "BEAR"] # Ribbon Filter
    
    best_score = -9999
    
    top_configs = []

    print("\n🚀 STARTING MULTI-DIMENSIONAL SNIPER OPTIMIZATION...")
    print(f"Testing {len(grid_price)*len(grid_vol)*len(grid_rsi)*len(grid_rib)} combinations...")
    
    ss_events = [e for e in raw_events if "SILENT" in e['type']]
    
    for p_lim, v_lim, rsi_lim, rib_mode in itertools.product(grid_price, grid_vol, grid_rsi, grid_rib):
        # APPLY FILTER
        filtered = []
        for e in ss_events:
            # 1. Price Range & Volume
            if e['p_range'] <= p_lim and e['vol_ratio'] >= v_lim:
                # 2. RSI Check
                if e['rsi'] <= rsi_lim:
                    # 3. Ribbon Check
                    if rib_mode == "ANY":
                        filtered.append(e)
                    elif rib_mode == "BULL" and e['ribbon_bull']:
                        filtered.append(e)
                    elif rib_mode == "BEAR" and not e['ribbon_bull']:
                        filtered.append(e)
                
        if len(filtered) < 5: continue 
        
        # STATS
        count = len(filtered)
        gems = sum(1 for e in filtered if e['outcome_24h'] >= 20.0) 
        garbage = sum(1 for e in filtered if e['outcome_24h'] < 5.0)
        win_rate = ((count - garbage) / count) * 100
        
        if win_rate < 30.0:
             score = 0
        else:
             score = (win_rate * 10) + (gems * 5)
        
        if score > 0:
            top_configs.append({
                'config': f"Range<={p_lim}%, Vol>={v_lim}x, RSI<={rsi_lim}, Rib={rib_mode}",
                'score': score,
                'stats': {'count': count, 'gems': gems, 'wr': win_rate}
            })

    # Sort and Print Top 3
    top_configs.sort(key=lambda x: x['score'], reverse=True)
    
    if not top_configs:
        print("❌ No configuration found with Win Rate > 30% and min 5 signals.")
    else:
        print("\n🏆 TOP 5 MULTI-DIMENSIONAL CONFIGURATIONS")
        print("=" * 70)
        for i, res in enumerate(top_configs[:5]):
            s = res['stats']
            print(f"#{i+1}: {res['config']}")
            print(f"    Win Rate : {s['wr']:.1f}%  (Garbage: {s['count'] - (s['count']*s['wr']/100):.0f}/{s['count']})")
            print(f"    Gems Found: {s['gems']} / {total_diamonds}")
            print("-" * 70)
    
if __name__ == "__main__":
    run_optimizer()
