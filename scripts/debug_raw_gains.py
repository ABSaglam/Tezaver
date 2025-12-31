from tezaver.core.rally_store import RallyStore
import pandas as pd

store = RallyStore()
all_rallies = store.list_rallies(limit=100000)

diamond_15m = [r for r in all_rallies if r.get('tier') == 'DIAMOND' and r.get('timeframe') == '15m']

print(f"Total Diamond 15m Rallies: {len(diamond_15m)}")
print("-" * 50)

gains = []
for r in diamond_15m[:10]: # Check first 10
    raw = r.get('raw_data', {}) or {}
    gain = raw.get('future_max_gain_pct')
    
    print(f"Rally: {r['id']}")
    print(f"  Raw Gain Value: {gain} (Type: {type(gain)})")
    
    # Check threshold logic
    decimal_check = gain > 0.05
    percent_check = gain > 5.0
    print(f"  > 0.05 (5% decimal): {decimal_check}")
    print(f"  > 5.0  (5% scaled):  {percent_check}")
    print("-" * 20)
