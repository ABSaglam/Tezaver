import json
import pandas as pd

def diagnose_aca_signatures():
    with open("data/aca_journey_memory.json", "r") as f:
        memory = json.load(f)
    with open("data/aca_lockstate_profiles.json", "r") as f:
        profiles = json.load(f)

    stats = []
    for r in memory:
        t_1_day = (pd.Timestamp(r['rally_date']) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        if t_1_day in profiles:
            p = profiles[t_1_day]
            stats.append(p)
            
    df = pd.DataFrame(stats)
    print("📊 ACA T-1 CATEGORY FREQUENCIES (362 Rallies):")
    for col in df.columns:
        print(f"\n[{col.upper()}]:")
        print(df[col].value_counts(normalize=True).mul(100).round(1).astype(str) + '%')

if __name__ == "__main__":
    diagnose_aca_signatures()
