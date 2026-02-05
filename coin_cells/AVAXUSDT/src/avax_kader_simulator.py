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
import avax_learn_core # Reuse feature calc logic

CONFIG_RULES_PATH = "/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn/rules"

def load_rules():
    base = Path(CONFIG_RULES_PATH)
    with open(base / "avax_fail_rules.json") as f: fail = json.load(f)
    with open(base / "avax_success_corridor.json") as f: success = json.load(f)
    with open(base / "avax_intraday_cancel_rules.json") as f: cancel = json.load(f)
    with open(base / "avax_trigger_map.json") as f: trig = json.load(f)
    return fail, success, cancel, trig

def evaluate_day(row, fail_rules, success_corridor):
    """
    Kader Tayini:
    1. Hard Veto? -> NO
    2. Success Corridor? -> NET_ADAY or WATCH
    """
    # 1. Fail Veto
    audit_verdict = "ONY"
    output = "WATCH" # Default start
    tier = "GOLD"
    reasons = []
    
    for col, limits in fail_rules.items():
        val = row.get(col)
        if val is None or pd.isna(val): continue
        
        if 'min_hard' in limits and val < limits['min_hard']:
            return "NO", "SILVER", "RED", f"{col}_LOW_VETO"
        if 'max_hard' in limits and val > limits['max_hard']:
            return "NO", "SILVER", "RED", f"{col}_HIGH_VETO"
            
    # 2. Success Corridor (Bonus for Upgrade)
    in_corridor = True
    for col, bands in success_corridor.items():
        val = row.get(col)
        if val is None or pd.isna(val): continue
        
        if val < bands['min'] or val > bands['max']:
            in_corridor = False
            reasons.append(f"{col}_OUT_CORRIDOR")
            
    # Simple Logic: If in corridor -> DIAMOND/NET_ADAY
    if in_corridor:
        # Check Trigger (Simulation: assume random trigger success for now if Micro_Trig is not fully calculated)
        # In a real run, Micro_Trig comes from 15m scanning.
        # Here we simulate Micro_Trig as True if Energy_Gap is healthy (>0)
        if row['Energy_Gap'] > 0:
            return "NET_ADAY", "DIAMOND", "ONY", "CORRIDOR_MATCH"
        else:
            return "WATCH", "GOLD", "RED", "WEAK_TRIGGER"
            
    return "WATCH", "GOLD", "RED", " ".join(reasons)

def run_simulation():
    print("::: Starting Kader Simulator :::")
    
    # 1. Load Rules
    fail_rules, success_corridor, _, _ = load_rules()
    print("Rules Loaded.")
    
    # 2. Load Data & Features
    # We allow re-calculations to ensure V17 freshness
    data_bundle = utils_io.get_data_bundle("AVAXUSDT")
    df = avax_learn_core.calculate_technical_features(data_bundle['1d'], None, None, None)
    df = avax_learn_core.generate_labels(df) # Labels only for validation
    
    # 3. Test Split (Last 100 Days)
    # Ensure sequential
    df_test = df.iloc[-100:].copy()
    print(f"Test Set: {len(df_test)} days (From {df_test['datetime'].iloc[0]} to {df_test['datetime'].iloc[-1]})")
    
    results = []
    
    for idx, row in df_test.iterrows():
        # Evaluate
        decision, tier, verdict, reason = evaluate_day(row, fail_rules, success_corridor)
        
        # Build V17 Row
        v17_row = {}
        for col in v17_schema.V17_COLUMNS:
            if col == "Date": v17_row[col] = row['datetime'].isoformat()
            elif col == "Symbol": v17_row[col] = "AVAXUSDT"
            elif col == "Tier": v17_row[col] = tier
            elif col == "Score": v17_row[col] = 0.5 # Placeholder
            elif col == "Audit_Verdict": v17_row[col] = verdict
            elif col in row: v17_row[col] = row[col]
            else: v17_row[col] = 0.0 # Default fallback
            
        # Add Decision Metadata (not in V17 but for CSV reporting we might add extra cols or just keep standard)
        # User said: V17 CANONIC. So we must put decision in "Tier" or similar. 
        # Actually user asked for "AVAX_NET_ADAY_REPORT.csv", which implies filtering.
        
        v17_row['Decision'] = decision # Internal usage
        v17_row['Reason'] = reason
        results.append(v17_row)
        
    # 4. Reports
    df_results = pd.DataFrame(results)
    
    # Canonical V17 Report (Drop extra internal columns)
    df_v17_daily = df_results[v17_schema.V17_COLUMNS].copy()
    
    out_dir = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Save Daily V17
    df_v17_daily.to_csv(out_dir / "AVAX_V17_TEST_DAILY.csv", index=False)
    
    # Save Net Aday
    df_net = df_results[df_results['Decision'] == 'NET_ADAY']
    df_net[v17_schema.V17_COLUMNS].to_csv(out_dir / "AVAX_NET_ADAY_REPORT.csv", index=False)
    
    # Hit Rate Summary
    accuracy_csv = []
    for dec in ['NET_ADAY', 'WATCH', 'NO']:
        subset = df_results[df_results['Decision'] == dec]
        hits = subset[subset['Hit_10'] == 'YES']
        rate = len(hits) / len(subset) * 100 if len(subset) > 0 else 0
        accuracy_csv.append({
            "Decision": dec,
            "Count": len(subset),
            "Hits": len(hits),
            "Hit_Rate": rate
        })
        
    df_perf = pd.DataFrame(accuracy_csv)
    df_perf.to_csv(out_dir / "AVAX_PERFORMANCE_SUMMARY.csv", index=False)
    
    print("\n::: SIMULATION COMPLETE :::")
    print(df_perf)
    print(f"Reports saved to {out_dir}")

if __name__ == "__main__":
    run_simulation()
