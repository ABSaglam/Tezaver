import sys
import os
import pandas as pd
import numpy as np
import json
from pathlib import Path

current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

import utils_io
import avax_kader_simulator_elite

# Define Paths
RUNS_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn")
RULES_DIR = RUNS_DIR / "rules"
REPORTS_DIR = RUNS_DIR / "reports"

def run_mode_b_relaxation():
    print("::: MODE B: AVAX TRIGGER RELAXATION :::")
    
    # 1. Load Elite Rules (V2)
    with open(RULES_DIR / "avax_fail_rules.json") as f: fail = json.load(f)
    with open(RULES_DIR / "avax_success_corridor_v2.json") as f: success = json.load(f)
    with open(RULES_DIR / "avax_intraday_cancel_rules_v2.json") as f: cancel = json.load(f)
    with open(RULES_DIR / "avax_trigger_map_v2.json") as f: trig = json.load(f)
    
    # 2. Relax Trigger Logic
    # In V2 Elite (Strict), "elite_mode_logic" forces stricter volume near boundary.
    # In V3 Mode B, we soften this multiplier from 1.2 to 1.0 (no extra penalty)
    # AND we widen the 'boundary' concept so fewer things are flagged as 'boundary'.
    
    if "elite_mode_logic" in trig:
        logic = trig["elite_mode_logic"]
        print(f"Original logic: {logic}")
        
        # RELAXATION:
        # 1. Reduce strict vol requirement (1.2 -> 1.05)
        logic["strict_vol_multiplier"] = 1.05 
        # 2. Shrink 'danger zone' definition (0.10 -> 0.05). Closer to edge is okay now.
        logic["boundary_proximity_threshold"] = 0.05 
        
        print(f"Relaxed logic: {logic}")
        trig["elite_mode_logic"] = logic
        
    # 3. Micro-Relaxation of Corridor (Optional but requested "Trigger Relax")
    # If users meant just trigger, we keep corridor same.
    # But often "Mode B" implies slightly more candidates. 
    # Let's keep corridor mostly same but ensure ADX upper bound is definitely 100 
    # (which we did in V3 fix already, but let's confirm).
    if 'ADX' in success:
        success['ADX']['max'] = 100.0
        
    # 4. Run Simulation with Modified Rules (InMemory)
    print("Running Simulation with Relaxed Rules...")
    data_bundle = utils_io.get_data_bundle("AVAXUSDT")
    import avax_learn_core
    df = avax_learn_core.calculate_technical_features(data_bundle['1d'], None, None, None)
    df = avax_learn_core.generate_labels(df)
    
    # Test Split
    df_test = df.iloc[-100:].copy()
    
    results = []
    
    for idx, row in df_test.iterrows():
        # Using the standard elite evaluator but with relaxed rule objects
        decision, tier, verdict, reason = avax_kader_simulator_elite.evaluate_elite_day(row, fail, success, cancel, trig)
        
        # Override output filenames in loop? No, just collect results
        v17_row = row.copy() # Contains labels
        # Ensure V17 cols
        out_row = {}
        for col in [
            "Date","Symbol","Tier","Score",
            "ADX","ATR_Norm","Ang_Price","Ang_EMA","Dist_EMA","Wick_Ratio",
            "Vrsi","V-Mom","Vol_Ratio","Volt_Ratio","Energy_Gap",
            "Micro_Trig","Ignition_Type","M15_RSI","M15_Vol",
            "Max_Excursion","Close_Excursion","Drawdown","Hit_10",
            "Anti_Penalty","Drift_Factor","Audit_Verdict"
        ]:
            if col == "Date": out_row[col] = row['datetime'].isoformat()
            elif col == "Symbol": out_row[col] = "AVAXUSDT"
            elif col == "Tier": out_row[col] = tier
            elif col == "Audit_Verdict": out_row[col] = verdict
            elif col in row: out_row[col] = row[col]
            else: out_row[col] = 0.0
            
        out_row['Decision'] = decision
        results.append(out_row)
        
    df_results = pd.DataFrame(results)
    
    # Save V3 Report
    df_net = df_results[df_results['Decision'] == 'NET_ADAY']
    out_path = REPORTS_DIR / "AVAX_NET_ADAY_REPORT_ELITE_V3.csv" 
    df_net.to_csv(out_path, index=False)
    
    print(f"Generated Mode B Report: {out_path}")
    print(f"Candidates Count: {len(df_net)}")

if __name__ == "__main__":
    run_mode_b_relaxation()
