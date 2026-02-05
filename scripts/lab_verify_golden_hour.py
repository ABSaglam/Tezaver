#!/usr/bin/env python3
"""
TEZAVER LAB: GOLDEN HOUR VERIFICATION
Testing the "Forensic" Hypothesis:
1. Time: 13:00 - 16:00 UTC (US Open)
2. Volume: 2.0x - 5.0x (Moderate, not extreme)
3. RSI: < 45
4. MACD: < 0
"""

import json

def verify_hypothesis():
    try:
        with open("temp_paradox_raw.json", "r") as f:
            events = json.load(f)
    except:
        print("No data.")
        return

    print(f"Loaded {len(events)} events.")
    
    # Filter: SILENT SCREAM ONLY
    events = [e for e in events if "SILENT" in e['type']]
    
    golden_events = []
    
    for e in events:
        # 1. Parse Metrics
        # desc: "R=1.1%, V=11.1x"
        pass # keys are already in dict if it came from latest scanner
        
        # Check if keys exist (Feather Fall might not have them)
        if 'rsi' not in e: continue
        
        # 2. TIME FILTER (13:00 - 16:00 UTC)
        # "2026-01-29 14:30:00"
        h = int(e['time'].split(' ')[1].split(':')[0])
        is_golden_hour = 13 <= h <= 16
        
        # 3. VOL FILTER (Moderate)
        is_moderate_vol = 2.0 <= e['vol_ratio'] <= 5.0
        
        # 4. RSI FILTER
        is_dip = e['rsi'] < 45
        
        # 5. MACD FILTER
        is_bear_mom = e['macd'] < 0
        
        if is_golden_hour and is_moderate_vol and is_dip:
            golden_events.append(e)
            
    # SUPER CLUSTER FILTER (Triple Tap)
    # Group by Symbol
    by_sym = {}
    for e in golden_events:
        if e['symbol'] not in by_sym: by_sym[e['symbol']] = []
        by_sym[e['symbol']].append(e)
        
    final_candidates = []
    for sym, evs in by_sym.items():
        if len(evs) >= 3: # TRIPLE TAP RULE
            # Add the FIRST signal of the cluster as the entry point
            final_candidates.append(evs[0])
            
    golden_events = final_candidates

    # STATS
    if not golden_events:
        print("No Triple Tap signals found.")
        return
        
    count = len(golden_events)
    gems = sum(1 for e in golden_events if e['outcome_24h'] >= 20.0)
    garbage = sum(1 for e in golden_events if e['outcome_24h'] < 5.0)
    win_rate = ((count - garbage) / count) * 100
    
    # Sort for printing
    golden_events.sort(key=lambda x: x['outcome_24h'], reverse=True)

    print("\n🧪 HYPOTHESIS TEST RESULTS (OPTIMAL)")
    print("=" * 60)
    print(f"Filter: 13-16h UTC + Vol 2-5x + Dip + COUNT >= 3")
    print(f"Clusters Found: {count}")
    print(f"Win Rate      : {win_rate:.1f}%")
    print(f"Gems Found    : {gems}")
    print("-" * 60)
    
    # List them
    golden_events.sort(key=lambda x: x['outcome_24h'], reverse=True)
    for i, e in enumerate(golden_events[:10]):
        print(f"#{i+1} {e['symbol']} (+{e['outcome_24h']:.1f}%): V={e['vol_ratio']:.1f}x, Time={e['time']}")

if __name__ == "__main__":
    verify_hypothesis()
