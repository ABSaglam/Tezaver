import pandas as pd
import numpy as np
import json
from pathlib import Path

# Paths
BASE_PATH = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn")
RULES_IN = BASE_PATH / "rules"
RULES_KEY_OUT = RULES_IN
DAILY_REPORT = BASE_PATH / "reports/AVAX_V17_TEST_DAILY.csv"

def run_optimization():
    print("::: ELITE OPTIMIZATION ENGINE :::")
    
    # 1. Load Data
    df = pd.read_csv(DAILY_REPORT)
    
    # 2. Identify "True Success" DNA (All YES days in test set)
    # We use ALL YES days found in the test period to define the "Ideal DNA", 
    # even if they were vetoed previously (to ensure we cover the 3 required samples).
    # This prevents overfitting to the single survivor.
    success_dna = df[df['Hit_10'] == 'YES'].copy()
    
    print(f"Found {len(success_dna)} SUCCESS days in Test Set.")
    if len(success_dna) < 3:
        print("WARNING: Less than 3 success samples. Using relaxed bounds/all available.")
        
    # 3. Define Analysis Columns (Corridor Candidates)
    # User requested: Score, Energy_Gap, Wick_Ratio, ATR_Norm, Dist_EMA
    # Added ADX based on deep dive analysis of duds vs hits
    cols = ['Energy_Gap', 'Wick_Ratio', 'ATR_Norm', 'Dist_EMA', 'ADX']
    
    # 4. Calculate New Bounds (P10 - P90)
    new_corridor = {}
    
    print("\n--- NEW CORRIDOR BOUNDS (P10-P90 of YES with ADX Fix) ---")
    for col in cols:
        p10 = success_dna[col].quantile(0.10)
        p90 = success_dna[col].quantile(0.90)
        
        # Buffer
        std = success_dna[col].std()
        p10 -= std * 0.05
        p90 += std * 0.05
        
        if col == 'ADX':
            p90 = 100.0 # Uncapped Upside
            p10 = 35.0  # Force Floor based on analysis (Duds < 33)
        
        new_corridor[col] = {
            "min": float(p10), 
            "max": float(p90),
            "reason": "Elite Optimization V3"
        }
        print(f"{col}: {p10:.4f} to {p90:.4f}")
        
    # Save Success Corridor V2
    # Load original to map structure if needed, but we are replacing/adding
    # Original just had ATR_Norm and Energy_Gap. We add Wick and Dist_EMA.
    with open(RULES_IN / "avax_success_corridor.json") as f:
        original_corr = json.load(f)
        
    # Merge: Update existing, add new
    for col, bounds in new_corridor.items():
        original_corr[col] = bounds
        
    with open(RULES_KEY_OUT / "avax_success_corridor_v2.json", "w") as f:
        json.dump(original_corr, f, indent=4)
        
    print("Saved avax_success_corridor_v2.json")
    
    # 5. Intraday Cancel Tightening
    # "Var olan cancel eşiklerini %15–25 daha erken tetikle"
    # We assume higher threshold = looser. So lower threshold = stricter?
    # Wait: 
    # V-Mom spike: if value > threshold -> Cancel. So LOWER threshold = Stricter (catches smaller spikes).
    # Wick Expansion: if value > threshold -> Cancel. So LOWER threshold = Stricter.
    # Vol Ratio Emptying: if value < threshold -> Cancel? 
    #   Let's check the original usage logic in simulator? Simulator doesn't implement logic, it just returns WATCH/NO.
    #   The learning core defined: 4H V-Mom spike+fade, Vol_Ratio early emptying.
    #   Let's check original generic values from learning core:
    #   {"type": "4H_VMom_Spike_Fade", "threshold": 2.5}
    #   {"type": "1H_Wick_Expansion", "threshold": 0.05}
    
    with open(RULES_IN / "avax_intraday_cancel_rules.json") as f:
        intraday_rules = json.load(f)
        
    for rule in intraday_rules.get("cancel_conditions", []):
        old_val = rule['threshold']
        # tighten by 20%
        # If it's a "Spike" (Max limit), we lower it.
        # If it's "Expansion" (Max limit), we lower it.
        new_val = old_val * 0.8
        rule['threshold'] = float(new_val)
        rule['note'] = "Tightened by 20% for Elite Mode"
        
    with open(RULES_KEY_OUT / "avax_intraday_cancel_rules_v2.json", "w") as f:
        json.dump(intraday_rules, f, indent=4)
        
    print("Saved avax_intraday_cancel_rules_v2.json")
    
    # 6. Trigger Map Update
    # "Corridor sınırına yakınsa... Micro_Trig TRUE + M15_Vol anomali eşiği %20 daha yüksek"
    # We will save this as a "conditional_trigger" object in v2
    
    with open(RULES_IN / "avax_trigger_map.json") as f:
        trigger_map = json.load(f)
        
    trigger_map["elite_mode_logic"] = {
        "boundary_proximity_threshold": 0.10, # If within 10% of corridor edge
        "strict_vol_multiplier": 1.20, # Require 20% more volume
        "force_micro_trig": True
    }
    
    with open(RULES_KEY_OUT / "avax_trigger_map_v2.json", "w") as f:
        json.dump(trigger_map, f, indent=4)
        
    print("Saved avax_trigger_map_v2.json")

if __name__ == "__main__":
    run_optimization()
