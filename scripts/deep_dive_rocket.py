#!/usr/bin/env python3
"""
Deep Dive: ROCKET Cluster Analysis
----------------------------------
Analyzes the 109 ROCKET coins to understand their specific behavior within Ayaş Tüneli.
Focuses on:
1. Signal Reliability: How often do they actually perform?
2. Conversion Rate: What % of signals reach Diamond?
3. Top Performers: Which specific ROCKET coins are the "Kings"?
"""

import pandas as pd
import numpy as np
import re
from pathlib import Path
from collections import defaultdict
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

def parse_rallies(report_path):
    with open(report_path, 'r') as f:
        content = f.read()
    
    rallies = []
    
    # Matches: DATE | X sin | ... | ... | SYMBOL(TIER+GAIN%), ...
    # We need to extract the line to get the date if possible, but for now just pulling raw signals
    # Regex for signal items: SYMBOL(TYPE+GAIN%) or SYMBOL(-TYPE:-LOSS%)
    
    # Positive: ACT(G+5%), AIXBT(S+24%)
    pos_pattern = r'(\w+)\((D|G|S)\+(\d+)%\)'
    for m in re.finditer(pos_pattern, content):
        rallies.append({
            'symbol': m.group(1) + "USDT",
            'tier': {'D': 'DIAMOND', 'G': 'GOLD', 'S': 'SILVER'}[m.group(2)],
            'gain': int(m.group(3)),
            'type': 'WIN'
        })
        
    # Negative: GHST(-BRONZE:-7%)
    neg_pattern = r'(\w+)\(-(\w+):-(\d+)%\)'
    for m in re.finditer(neg_pattern, content):
        rallies.append({
            'symbol': m.group(1) + "USDT",
            'tier': m.group(2), # BRONZE, SILVER, IRON, etc.
            'gain': -int(m.group(3)),
            'type': 'LOSS'
        })
        
    return pd.DataFrame(rallies)

def main():
    print("🚀 ROCKET CLUSTER DEEP DIVE")
    print("=" * 60)
    
    # 1. Load Data
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        rallies = parse_rallies('analysis/ayas_tuneli_2y_120h_rapor.md')
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    # 2. Filter for ROCKET Cluster
    rocket_symbols = dna[dna['cluster_name'] == 'ROCKET']['symbol'].tolist()
    print(f"Total ROCKET Coins: {len(rocket_symbols)}")
    
    rocket_rallies = rallies[rallies['symbol'].isin(rocket_symbols)]
    print(f"Total Signals for ROCKET Coins: {len(rocket_rallies)}")
    
    if len(rocket_rallies) == 0:
        print("No signals found for ROCKET cluster!")
        return

    # 3. Analyze Performance
    # Group by Symbol
    stats = []
    
    for sym in rocket_symbols:
        sym_rallies = rocket_rallies[rocket_rallies['symbol'] == sym]
        if len(sym_rallies) == 0:
            continue
            
        total = len(sym_rallies)
        wins = len(sym_rallies[sym_rallies['type'] == 'WIN'])
        losses = len(sym_rallies[sym_rallies['type'] == 'LOSS'])
        
        diamonds = len(sym_rallies[sym_rallies['tier'] == 'DIAMOND'])
        golds = len(sym_rallies[sym_rallies['tier'] == 'GOLD'])
        silvers = len(sym_rallies[sym_rallies['tier'] == 'SILVER'])
        
        avg_gain = sym_rallies['gain'].mean()
        max_gain = sym_rallies['gain'].max()
        
        # Conversion Rate: Percentage of signals that hit DIAMOND
        diamond_conv = (diamonds / total) * 100
        
        stats.append({
            'symbol': sym.replace('USDT', ''),
            'total': total,
            'win_rate': (wins/total)*100,
            'diamond_cnt': diamonds,
            'gold_cnt': golds,
            'silver_cnt': silvers,
            'loss_cnt': losses,
            'diamond_prob': diamond_conv,
            'avg_gain': avg_gain,
            'max_gain': max_gain
        })
    
    df_stats = pd.DataFrame(stats)
    
    # 4. Identify Sub-Categories within ROCKET
    print("\n🏆 THE KINGS (High Diamond Probability > 30% & > 5 signals)")
    kings = df_stats[(df_stats['diamond_prob'] > 30) & (df_stats['total'] >= 5)].sort_values('diamond_prob', ascending=False)
    print(kings[['symbol', 'total', 'diamond_cnt', 'diamond_prob', 'avg_gain']].to_markdown(index=False, floatfmt=".1f"))
    
    print("\n💣 THE GAMBLERS (High Max Gain but Low Win Rate)")
    # High potential but risky
    gamblers = df_stats[(df_stats['max_gain'] > 100) & (df_stats['win_rate'] < 70)].sort_values('max_gain', ascending=False)
    if not gamblers.empty:
        print(gamblers[['symbol', 'total', 'win_rate', 'max_gain', 'avg_gain']].head(10).to_markdown(index=False, floatfmt=".1f"))
    else:
        print("No pure gamblers found (Win rates are generally good!)")

    print("\n🛡️ RELIABLE ROCKETS (Win Rate > 90% & > 5 signals)")
    reliable = df_stats[(df_stats['win_rate'] > 90) & (df_stats['total'] >= 5)].sort_values('total', ascending=False)
    print(reliable[['symbol', 'total', 'win_rate', 'avg_gain', 'max_gain']].head(10).to_markdown(index=False, floatfmt=".1f"))
    
    # 5. Global ROCKET Stats
    print("\n📊 GLOBAL ROCKET STATS")
    print(f"Overall Win Rate: {(len(rocket_rallies[rocket_rallies['type'] == 'WIN']) / len(rocket_rallies) * 100):.1f}%")
    print(f"Diamond Rate: {(len(rocket_rallies[rocket_rallies['tier'] == 'DIAMOND']) / len(rocket_rallies) * 100):.1f}%")
    print(f"Average Gain: {rocket_rallies['gain'].mean():.1f}%")

    # Save
    output_path = 'library/rally_dna/rocket_cluster_deep_dive.csv'
    df_stats.sort_values('diamond_prob', ascending=False).to_csv(output_path, index=False)
    print(f"\n📁 Saved details to {output_path}")

if __name__ == "__main__":
    main()
