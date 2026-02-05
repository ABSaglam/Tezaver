import json
import pandas as pd
import numpy as np
from pathlib import Path

def generate_master_report():
    profile_dir = Path("DNA_Profiles")
    with open(profile_dir / "coin_DNA_profile.json", "r") as f:
        dna_manifest = json.load(f)
    
    master_data = []
    for symbol, profiles in dna_manifest.items():
        tier_counts = {1: 0, 2: 0, 3: 0}
        avg_exp = []
        behavioral_notes = []
        
        for p in profiles:
            tier_counts[p.get('tier', 3)] += 1
            avg_exp.append(p['expansion_ratio'])
            
        # Qualitative notes based on DNA characteristics
        avg_vol_contraction = np.mean([p['dna'].get('1d', {}).get('vol_contraction', 1) for p in profiles])
        if avg_vol_contraction < 0.5:
            behavioral_notes.append("High volume contraction before expansion.")
        else:
            behavioral_notes.append("Standard volume profile.")
            
        master_data.append({
            "Symbol": symbol,
            "Total Expansions (23-25)": len(profiles),
            "Tier 1 Count": tier_counts[1],
            "Tier 2 Count": tier_counts[2],
            "Tier 3 Count": tier_counts[3],
            "Avg Expansion %": round(np.mean(avg_exp) * 100, 2),
            "Behavioral Notes": " ".join(behavioral_notes)
        })
        
    df_master = pd.DataFrame(master_data)
    df_master.to_csv("Reports/DNA_MASTER_REPORT.csv", index=False)
    print("DNA_MASTER_REPORT.csv generated in Reports/")

if __name__ == "__main__":
    generate_master_report()
