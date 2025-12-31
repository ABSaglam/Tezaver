#!/usr/bin/env python3
"""
Price Data Coverage Analysis - After Path Fix
==============================================
Check coverage using CORRECT path
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tezaver.core.rally_store import RallyStore
from tezaver.core import coin_cell_paths

store = RallyStore()
all_rallies = store.list_rallies(limit=100000)

print("=" * 80)
print("PRICE DATA COVERAGE - AFTER PATH FIX")
print("=" * 80)
print(f"\nTotal rallies: {len(all_rallies)}")

# Stats by tier
tier_stats = {}

for rally in all_rallies:
    tier = rally.get('tier', 'UNKNOWN')
    tf = rally.get('timeframe', 'UNKNOWN')
    symbol = rally.get('symbol', 'UNKNOWN')
    
    key = f"{tier}_{tf}"
    
    if key not in tier_stats:
        tier_stats[key] = {
            'total': 0,
            'with_data': 0,
            'without_data': 0,
            'missing_coins': set()
        }
    
    tier_stats[key]['total'] += 1
    
    # Check using CORRECT path helper
    try:
        data_file = coin_cell_paths.get_history_file(symbol, tf)
        
        if data_file.exists():
            tier_stats[key]['with_data'] += 1
        else:
            tier_stats[key]['without_data'] += 1
            tier_stats[key]['missing_coins'].add(symbol)
    except Exception as e:
        tier_stats[key]['without_data'] += 1
        tier_stats[key]['missing_coins'].add(symbol)

# Summary by tier
print("\n" + "=" * 80)
print("TIER SUMMARY")
print("=" * 80)

for tier in ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE']:
    tier_total = 0
    tier_with_data = 0
    
    for tf in ['15m', '1h', '4h']:
        key = f"{tier}_{tf}"
        if key in tier_stats:
            stats = tier_stats[key]
            tier_total += stats['total']
            tier_with_data += stats['with_data']
    
    if tier_total > 0:
        pct = (tier_with_data / tier_total * 100)
        status = "✅" if pct > 80 else "⚠️" if pct > 50 else "❌"
        print(f"{status} {tier:8s}: {tier_with_data:5d}/{tier_total:5d} rallies ({pct:5.1f}%)")

# Overall
total = sum(s['total'] for s in tier_stats.values())
with_data = sum(s['with_data'] for s in tier_stats.values())
without_data = sum(s['without_data'] for s in tier_stats.values())

print("\n" + "=" * 80)
print("OVERALL")
print("=" * 80)
print(f"Total:        {total}")
print(f"WITH data:    {with_data} ({with_data/total*100:.1f}%)")
print(f"WITHOUT data: {without_data} ({without_data/total*100:.1f}%)")

# Missing coins
all_missing = set()
for stats in tier_stats.values():
    all_missing.update(stats['missing_coins'])

if all_missing:
    print(f"\nMissing coins ({len(all_missing)}): {', '.join(sorted(all_missing))}")

print("\n" + "=" * 80)
if with_data == total:
    print("✅ PERFECT: All rallies have price data!")
elif with_data / total > 0.9:
    print(f"✅ EXCELLENT: {with_data/total*100:.1f}% coverage")
elif with_data / total > 0.5:
    print(f"⚠️  GOOD: {with_data/total*100:.1f}% coverage")
else:
    print(f"❌ POOR: Only {with_data/total*100:.1f}% coverage")
print("=" * 80)
