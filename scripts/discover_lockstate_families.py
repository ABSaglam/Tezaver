import json
import pandas as pd

def discover_families():
    # Load Memory & Profiles
    with open("data/algo_journey_memory.json", "r") as f:
        memory = json.load(f)
    with open("data/algo_lockstate_profiles.json", "r") as f:
        all_profiles = json.load(f)
        
    eligible_families = []
    
    for r in memory:
        # We look at the profile on the day BEFORE the rally (T-1) as the primary 'Lock'
        # and also T-3, T-5 for historical context.
        # But for 'The Key', we focus on the state at the start of the rally day.
        
        # Journey days defined in Stage 1: [T-1, T-3, T-5, T-7, T-14, T-21]
        for j_day in r['journey_days']:
            if j_day in all_profiles:
                p = all_profiles[j_day]
                # Combine 5 dimensions into a single key
                family_key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafıza']}"
                eligible_families.append(family_key)
                
    # Count frequency of each family
    family_counts = pd.Series(eligible_families).value_counts().to_dict()
    
    # Save Families
    with open("data/algo_lockstate_families.json", "w") as f:
        json.dump(family_counts, f, indent=2)
        
    print(f"✅ Discovered {len(family_counts)} Unique Profile Families that led to rallies.")
    print("\nTop 5 Families:")
    for i, (fam, count) in enumerate(list(family_counts.items())[:5]):
        print(f"{i+1}. {fam} -> {count} times")

if __name__ == "__main__":
    discover_families()
