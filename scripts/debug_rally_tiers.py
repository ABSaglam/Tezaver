#!/usr/bin/env python3
"""
Debug script to inspect rally data and tier filtering
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tezaver.core.rally_store import RallyStore
import json

store = RallyStore()
rallies = store.list_rallies(limit=100)

print(f"Total rallies: {len(rallies)}")
print("\n" + "=" * 70)
print("TIER DISTRIBUTION:")
print("=" * 70)

tier_counts = {}
tier_samples = {}

for rally in rallies:
    tier = rally.get('tier')
    tier_type = type(tier).__name__
    tier_repr = repr(tier)
    
    key = f"{tier_repr} (type: {tier_type})"
    tier_counts[key] = tier_counts.get(key, 0) + 1
    
    if key not in tier_samples:
        tier_samples[key] = rally['id']

print("\nCounts:")
for tier_key, count in sorted(tier_counts.items(), key=lambda x: -x[1]):
    print(f"  {tier_key}: {count}")
    print(f"    Sample: {tier_samples[tier_key]}")

print("\n" + "=" * 70)
print("SAMPLE RALLIES:")
print("=" * 70)

for tier_name in ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE']:
    print(f"\n{tier_name} rallies:")
    found = False
    for rally in rallies[:20]:
        if rally.get('tier') == tier_name:
            print(f"  ✓ {rally['id']}")
            print(f"    tier field: {repr(rally.get('tier'))}")
            print(f"    timeframe: {rally.get('timeframe')}")
            print(f"    symbol: {rally.get('symbol')}")
            found = True
            break
    if not found:
        print(f"  ✗ No {tier_name} found in first 20")

print("\n" + "=" * 70)
print("FILTERING TEST:")
print("=" * 70)

target_tier = "DIAMOND"
target_tf = "15m"

print(f"\nFilter: tier={target_tier}, timeframe={target_tf}")

matches = []
for rally in rallies:
    if rally.get('tier') == target_tier and rally.get('timeframe') == target_tf:
        matches.append(rally)

print(f"Matched: {len(matches)} rallies")

if matches:
    print("\nFirst 5 matches:")
    for r in matches[:5]:
        print(f"  - {r['id']} ({r.get('symbol')})")
else:
    print("\nNo matches!")
    print("\nDEBUG: Checking why...")
    
    # Check tier match
    tier_match_count = sum(1 for r in rallies if r.get('tier') == target_tier)
    print(f"  Rallies with tier={target_tier}: {tier_match_count}")
    
    # Check timeframe match
    tf_match_count = sum(1 for r in rallies if r.get('timeframe') == target_tf)
    print(f"  Rallies with timeframe={target_tf}: {tf_match_count}")
    
    # Check both
    both_match = [r for r in rallies if r.get('tier') == target_tier]
    if both_match:
        print(f"\n  Sample DIAMOND rally timeframes:")
        for r in both_match[:5]:
            print(f"    {r['id']}: tf={repr(r.get('timeframe'))}")
