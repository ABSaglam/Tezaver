from tezaver.core.rally_store import RallyStore
import pandas as pd

store = RallyStore()
all_rallies = store.list_rallies(limit=100000)

diamond_15m = [r for r in all_rallies if r.get('tier') == 'DIAMOND' and r.get('timeframe') == '15m']

print(f"Total Diamond 15m Rallies: {len(diamond_15m)}")
print("-" * 50)

gains = []
for r in diamond_15m:
    raw = r.get('raw_data', {}) or {} # Handle None
    gain = raw.get('future_max_gain_pct', 0.0)
    gains.append(gain)
    print(f"Rally: {r['id']} | Gain: {gain:.2f}%")

s = pd.Series(gains)
print("-" * 50)
print(f"Max Gain: {s.max():.2f}%")
print(f"Mean Gain: {s.mean():.2f}%")
print(f"Rallies > 5%: {(s > 5.0).sum()}")
