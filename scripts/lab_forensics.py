#!/usr/bin/env python3
"""
TEZAVER LAB: FORENSICS
Dissecting the Winners to find the DNA of Success.
"""

import json
import statistics
import pandas as pd
from datetime import datetime

def analyze_winners():
    try:
        with open("temp_paradox_raw.json", "r") as f:
            events = json.load(f)
    except:
        print("No data found.")
        return

    # Filter Winners (> 10%)
    winners = [e for e in events if e['outcome_24h'] >= 10.0]
    losers = [e for e in events if e['outcome_24h'] < 0.0] # True Losers
    
    print(f"Total Events: {len(events)}")
    print(f"Winners (>10%): {len(winners)}")
    print(f"Losers (<0%): {len(losers)}")
    print("-" * 60)
    
    if not winners:
        print("No winners to analyze.")
        return

    # 1. METRIC COMPARISON
    metrics = ['p_range', 'vol_ratio', 'rsi', 'macd']
    
    print(f"{'METRIC':<15} | {'WINNERS AVG':<15} | {'LOSERS AVG':<15} | {'DIFF':<10}")
    print("-" * 60)
    
    for m in metrics:
        if m not in winners[0]: continue
        
        w_vals = [e.get(m, 0) for e in winners]
        l_vals = [e.get(m, 0) for e in losers]
        
        w_avg = statistics.mean(w_vals)
        l_avg = statistics.mean(l_vals)
        diff = ((w_avg - l_avg) / l_avg) * 100 if l_avg != 0 else 0
        
        print(f"{m:<15} | {w_avg:<15.4f} | {l_avg:<15.4f} | {diff:+.1f}%")

    # 2. RIBBON ANALYSIS
    print("-" * 60)
    w_bull = sum(1 for e in winners if e.get('ribbon_bull'))
    l_bull = sum(1 for e in losers if e.get('ribbon_bull'))
    
    print(f"Ribbon BULL Ratio (Winners): {w_bull}/{len(winners)} ({(w_bull/len(winners))*100:.1f}%)")
    print(f"Ribbon BULL Ratio (Losers) : {l_bull}/{len(losers)} ({(l_bull/len(losers))*100:.1f}%)")
    
    # 3. TIME OF DAY ANALYSIS
    print("-" * 60)
    print("WINNER HOURS (UTC):")
    hours = {}
    for e in winners:
        # Time format: 2026-01-29 07:15:00
        h = int(e['time'].split(' ')[1].split(':')[0])
        hours[h] = hours.get(h, 0) + 1
        
    for h in sorted(hours.keys()):
        print(f"{h:02d}:00 -> {hours[h]} wins")

    # 4. TOP 10 WINNERS
    print("-" * 60)
    print("TOP 10 WINNERS PROFILE:")
    winners.sort(key=lambda x: x['outcome_24h'], reverse=True)
    for i, w in enumerate(winners[:10]):
        rib = "BULL" if w.get('ribbon_bull') else "BEAR"
        print(f"#{i+1} {w['symbol']} ({w['outcome_24h']:.1f}%): RSI={w['rsi']:.1f}, Vol={w['vol_ratio']:.1f}x, Range={w['p_range']:.2f}%, Rib={rib}, MACD={w['macd']:.4f}")

if __name__ == "__main__":
    analyze_winners()
