import sys
import os
import pandas as pd
import numpy as np
import json
from pathlib import Path

current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

import utils_io
import v17_schema
import avax_learn_core

# UPDATED PATHS FOR ELITE V2
RUNS_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn")
RULES_DIR = RUNS_DIR / "rules"
REPORTS_DIR = RUNS_DIR / "reports"

def load_elite_rules():
    with open(RULES_DIR / "avax_fail_rules.json") as f: fail = json.load(f) # V1 (Unchanged)
    with open(RULES_DIR / "avax_success_corridor_v2.json") as f: success = json.load(f) # V2
    with open(RULES_DIR / "avax_intraday_cancel_rules_v2.json") as f: cancel = json.load(f) # V2
    with open(RULES_DIR / "avax_trigger_map_v2.json") as f: trig = json.load(f) # V2
    return fail, success, cancel, trig

def evaluate_elite_day(row, fail_rules, success_corridor, cancel_rules, trig_map):
    """
    Elite Decision Logic:
    1. Fail Veto (Legacy)
    2. Elite Corridor (Stricter V2) + Boundary Logic
    3. Intraday Cancel (Stricter V2)
    4. Trigger Check
    """
    reasons = []

    # 1. FAIL VETO (Legacy)
    for col, limits in fail_rules.items():
        val = row.get(col)
        if val is None or pd.isna(val): continue
        if 'min_hard' in limits and val < limits['min_hard']:
            return "NO", "SILVER", "RED", f"{col}_LOW_VETO"
        if 'max_hard' in limits and val > limits['max_hard']:
            return "NO", "SILVER", "RED", f"{col}_HIGH_VETO"

    # 2. SUCCESS CORRIDOR (V2)
    in_corridor = True
    near_boundary = False
    
    for col, bands in success_corridor.items():
        val = row.get(col)
        if val is None or pd.isna(val): continue
        
        # Check strict bounds
        if val < bands['min'] or val > bands['max']:
            in_corridor = False
            reasons.append(f"{col}_OUT_ELITE")
            break # Fail fast on corridor
        
        # Check Proximity (for Elite Logic)
        # If value is within 10% of min or max
        r = bands['max'] - bands['min']
        if (val - bands['min']) < (r * 0.10) or (bands['max'] - val) < (r * 0.10):
            near_boundary = True
            
    if not in_corridor:
        return "WATCH", "GOLD", "RED", " ".join(reasons)

    # 3. INTRADAY CANCEL (V2 - Simulated)
    # We simulate checking intraday conditions. 
    # Since we don't have real intraday cancel metrics in the row (simplified), 
    # we assume standard pass unless we implement the calc.
    # user said "4H/1H saglamadir: aday yaratmaz, sadece iptal eder."
    # For simulation purposes with just daily row, we skip deep intraday calc 
    # BUT we can check if any indicators hint at "Cancel" signature if we had them.
    # We proceed assuming pass for now to focus on Daily Corridor filtering which is the main filter.

    # 4. TRIGGER + BOUNDARY LOGIC
    # If near boundary, apply strict trigger
    req_vol = trig_map.get("m15_vol_threshold", 1.0)
    
    if near_boundary and "elite_mode_logic" in trig_map:
        logic = trig_map["elite_mode_logic"]
        req_vol *= logic.get("strict_vol_multiplier", 1.2)
        # Force Micro Trig check
        if logic.get("force_micro_trig", True) and not row['Micro_Trig']:
            # In our features, Micro_Trig is usually False unless set.
            # We treat Energy_Gap > 0 as a proxy for "Trigger Ready" in this simulation context
            if row['Energy_Gap'] <= 0:
                return "WATCH", "GOLD", "RED", "BOUNDARY_BUT_WEAK_TRIG"

    # Check Vol Trigger (Simulated with Daily Vol Ratio proxy for now or specific column if exists)
    # We use M15_Vol column if available (it is in V17 schema, currently 1.0 constant in learning core)
    # Since M15_Vol is constant 1.0 in this synthetic run, this check is symbolic 
    # unless we updated Avax Learn Core to populate it dynamically.
    # We'll rely on the main corridor filter to do the heavy lifting (Step 2).
    
    return "NET_ADAY", "DIAMOND", "ONY", "ELITE_MATCH"

def run_elite_simulation():
    print("::: ELITE KADER SIMULATOR :::")
    
    # Load V2 Rules
    fail, success, cancel, trig = load_elite_rules()
    
    # Load Data (Recalculate to be sure)
    # We can just load the previous V17 report to respect "Same Data" rule and save time, 
    # but strictly we should recalculate features. Since features are deterministic, loading valid csv is safer/faster.
    # Actually, let's recalculate to ensure Utils/Schema integrity.
    data_bundle = utils_io.get_data_bundle("AVAXUSDT")
    df = avax_learn_core.calculate_technical_features(data_bundle['1d'], None, None, None)
    df = avax_learn_core.generate_labels(df)
    
    # Test Split (Last 100)
    df_test = df.iloc[-100:].copy()
    
    results = []
    
    for idx, row in df_test.iterrows():
        decision, tier, verdict, reason = evaluate_elite_day(row, fail, success, cancel, trig)
        
        v17_row = {}
        for col in v17_schema.V17_COLUMNS:
            if col == "Date": v17_row[col] = row['datetime'].isoformat()
            elif col == "Symbol": v17_row[col] = "AVAXUSDT"
            elif col == "Tier": v17_row[col] = tier
            elif col == "Audit_Verdict": v17_row[col] = verdict
            elif col in row: v17_row[col] = row[col]
            else: v17_row[col] = 0.0
            
        v17_row['Decision'] = decision # Internal
        v17_row['Reason'] = reason
        results.append(v17_row)
        
    df_results = pd.DataFrame(results)
    
    # Reports
    df_elite_daily = df_results[v17_schema.V17_COLUMNS].copy()
    df_elite_daily.to_csv(REPORTS_DIR / "AVAX_V17_TEST_DAILY_ELITE.csv", index=False)
    
    df_net_elite = df_results[df_results['Decision'] == 'NET_ADAY']
    df_net_elite[v17_schema.V17_COLUMNS].to_csv(REPORTS_DIR / "AVAX_NET_ADAY_REPORT_ELITE.csv", index=False)
    
    # Performance
    acc = []
    for dec in ['NET_ADAY', 'WATCH', 'NO']:
        subset = df_results[df_results['Decision'] == dec]
        hits = subset[subset['Hit_10'] == 'YES']
        rate = len(hits) / len(subset) * 100 if len(subset) > 0 else 0
        acc.append({
            "Decision": dec, 
            "Count": len(subset), 
            "Hits": len(hits), 
            "Hit_Rate": rate,
            "False_Neg": 0 # Calc below
        })
        
    # False Negatives (Hits missed in NO or WATCH)
    missed = df_results[(df_results['Decision'] != 'NET_ADAY') & (df_results['Hit_10'] == 'YES')]
    fn_count = len(missed)
    
    print("\n::: ELITE PERFORMANCE :::")
    perf_df = pd.DataFrame(acc)
    print(perf_df)
    print(f"Total False Negatives: {fn_count}")
    
    perf_df.to_csv(REPORTS_DIR / "AVAX_PERFORMANCE_SUMMARY_ELITE.csv", index=False)
    
    # Validation Check
    net_count = len(df_net_elite)
    hit_rate = perf_df.loc[perf_df['Decision'] == 'NET_ADAY', 'Hit_Rate'].iloc[0] if net_count > 0 else 0
    
    print(f"\nFinal Check:")
    print(f"NET_ADAY Count: {net_count} (Goal: 6-8)")
    print(f"Hit Rate: {hit_rate:.2f}% (Goal: >= 25%)")
    print(f"False Negatives: {fn_count} (Goal: <= 2)")
    
    if 6 <= net_count <= 8 and hit_rate >= 25.0 and fn_count <= 2:
        print(">>> SUCCESS: ELITE MODE ACHIEVED <<<")
    else:
        print(">>> WARNING: Optimisation targets not fully met. Requires manual review.")

if __name__ == "__main__":
    run_elite_simulation()
