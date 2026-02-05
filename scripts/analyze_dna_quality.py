import json
import numpy as np

with open('dna_manifest_v6.json', 'r') as f:
    manifest = json.load(f)

thresholds = [30, 40, 45, 50, 55, 60]
total_strats = 0
survivors = {t: 0 for t in thresholds}

for coin, strats in manifest.items():
    for s in strats:
        total_strats += 1
        wr = s['win_rate']
        for t in thresholds:
            if wr >= t:
                survivors[t] += 1

print(f"Total Strategies: {total_strats}")
print("-" * 30)
for t in thresholds:
    count = survivors[t]
    pct = (count / total_strats) * 100
    print(f"WR >= {t}%: {count} strategies ({pct:.1f}%)")
