import json
import pandas as pd

def discover_aca_families():
    # Load Memory & Profiles
    with open("data/aca_journey_memory.json", "r") as f:
        memory = json.load(f)
    with open("data/aca_lockstate_profiles.json", "r") as f:
        all_profiles = json.load(f)
        
    eligible_families = []
    
    for r in memory:
        for j_day in r['journey_days']:
            if j_day in all_profiles:
                p = all_profiles[j_day]
                family_key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafıza']}"
                eligible_families.append(family_key)
                
    family_counts = pd.Series(eligible_families).value_counts().to_dict()
    
    with open("data/aca_lockstate_families.json", "w") as f:
        json.dump(family_counts, f, indent=2)
        
    print(f"✅ Discovered {len(family_counts)} Unique ACA Profile Families that led to rallies.")
    print("\nTop 5 Families:")
    for i, (fam, count) in enumerate(list(family_counts.items())[:5]):
        print(f"{i+1}. {fam} -> {count} times")

if __name__ == "__main__":
    discover_aca_families()
