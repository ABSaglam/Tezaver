import sys
import pandas as pd
import numpy as np
import json
from pathlib import Path

# Setup Paths
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

import utils_io
import avax_learn_core
import core_indicators_v3
import v17_schema

BASE_OUT = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v3/runs/run_001")
RULES_DIR = BASE_OUT / "rules"
REPORTS_DIR = BASE_OUT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def load_v3_rules():
    with open(RULES_DIR / "avax_fail_rules_v3.json") as f: fail = json.load(f)
    with open(RULES_DIR / "avax_success_corridor_v3.json") as f: succ = json.load(f)
    with open(RULES_DIR / "avax_intraday_cancel_rules_v3.json") as f: cancel = json.load(f)
    with open(RULES_DIR / "avax_trigger_map_v3.json") as f: trig = json.load(f)
    return fail, succ, cancel, trig

def check_intraday_cancel(daily_row, df_4h_day, df_1h_day, cancel_rules):
    # 1. 4H Wick Ratio Rule
    # "wick_ratio_4h": {"threshold": 0.28}
    # Calc from df_4h_day
    if len(df_4h_day) > 0:
        body_top = df_4h_day[['open', 'close']].max(axis=1)
        hl = df_4h_day['high'] - df_4h_day['low']
        wicks = (df_4h_day['high'] - body_top) / hl
        wicks = wicks.fillna(0)
        avg_wick = wicks.mean()
        
        thr = cancel_rules.get("wick_ratio_4h", {}).get("threshold", 0.28)
        if avg_wick > thr:
            return True, f"CANCEL_4H_WICK ({avg_wick:.2f} > {thr})"
            
    # 2. 4H Ribbon Trap
    # "4h_ribbon_trap": {"condition": "RIBBON_INSIDE and RSI < RSI_EMA"}
    # Use pre-calculated states in df_4h_day
    # Logic: If MAJORITY of bars are trapped? Or ANY bar? 
    # Interpretation: "Trap" usually means we are stuck. 
    # Let's say if > 50% of bars are inside and suppressed.
    # Or simpler: if the last bar (close) is suppressed.
    # User's audit 11-24 said: "Inside + RSI Weak... persistence"
    # User's audit 11-30 said: "Price stuck inside ribbon"
    # Let's use a strict check: If Avg State is Suppression?
    # Let's use: If ANY bar is Ribbon Inside + RSI < EMA? No that's too common.
    # Let's use: If > 50% bars are Suppression Up.
    if len(df_4h_day) > 0:
        trap_count = len(df_4h_day[df_4h_day['STATE_RIBBON_SUPPRESSION_UP'] == True])
        if trap_count / len(df_4h_day) >= 0.5:
             return True, f"CANCEL_4H_RIBBON_TRAP ({trap_count}/{len(df_4h_day)} bars)"

    return False, "NONE"

def evaluate_day_v3(row, df_4h_day, df_1h_day, fail_rules, success_corridor, cancel_rules, trig_map):
    # Log Container
    stage_log = {
        "Date": row['datetime'].isoformat(),
        "DailyGatePass": False,
        "IntradayCancelApplied": False,
        "CancelReason": "NONE",
        "TriggerChecked": False,
        "FinalDecision": "NO",
        "Audit_Verdict": "RED",
        "Ignition_Type": "NONE"
    }
    
    reasons = []
    
    # --- STAGE 1: DAILY GATE ---
    # A. Hard Veto
    vetoed = False
    for col, limits in fail_rules.items():
        if col == "suppression_veto": continue
        val = row.get(col)
        if val is None: continue
        if 'min_hard' in limits and val < limits['min_hard']:
             reasons.append(f"{col}_LOW_VETO")
             vetoed = True
        if 'max_hard' in limits and val > limits['max_hard']:
             reasons.append(f"{col}_HIGH_VETO")
             vetoed = True
    
    # Suppression Veto
    supp_rule = fail_rules.get("suppression_veto", {})
    if supp_rule.get("active", False):
        if row.get('STATE_RIBBON_SUPPRESSION_UP', False):
             reasons.append("RIBBON_SUPPRESSION_VETO")
             vetoed = True # Watch level veto -> effective Fail for Net Aday

    # Corridor
    in_corridor = True
    for col, bands in success_corridor.items():
        val = row.get(col)
        if val is None: continue
        if val < bands['min'] or val > bands['max']:
             in_corridor = False
             reasons.append(f"{col}_OUT")

    daily_pass = (not vetoed) and in_corridor
    stage_log["DailyGatePass"] = daily_pass
    
    if not daily_pass:
        stage_log["FinalDecision"] = "WATCH" if in_corridor else "NO" # If vetoed but in corridor -> Watch? No, veto kills it.
        stage_log["FinalDecision"] = "NO" # Simplify
        return stage_log, "SILVER", "RED", " ".join(reasons)

    # --- STAGE 2: INTRADAY CANCEL (HARD) ---
    is_canceled, cancel_reason = check_intraday_cancel(row, df_4h_day, df_1h_day, cancel_rules)
    stage_log["IntradayCancelApplied"] = is_canceled
    stage_log["CancelReason"] = cancel_reason
    
    if is_canceled:
        stage_log["FinalDecision"] = "NO"
        stage_log["Audit_Verdict"] = "RED"
        return stage_log, "SILVER", "RED", cancel_reason

    # --- STAGE 3: TRIGGER ---
    # Placeholder for actual 15m trigger check logic
    # We assume passed if daily is good unless specific logic
    # User said: "15M Trigger (son kapı): ... Trigger onayı olmadan NET_ADAY yazma."
    # For now, we use 'Micro_Trig' column from V17 which simulates a basic trigger check.
    # If Micro_Trig is False -> NO?
    # In V3 construction, we said "If Daily Locked... trust trigger."
    stage_log["TriggerChecked"] = True
    
    # Let's be strict: If Micro_Trig is False, it's WATCH, not NET_ADAY
    if row.get('Micro_Trig') == False:
         # Check Lock
         is_locked = row.get('STATE_RSI_LOCK_UP', False) or row.get('STATE_RIBBON_BREAK_UP', False)
         if not is_locked:
             stage_log["FinalDecision"] = "WATCH"
             return stage_log, "GOLD", "RED", "NO_TRIGGER_NO_LOCK"
             
    # SUCCESS
    stage_log["FinalDecision"] = "NET_ADAY"
    stage_log["Audit_Verdict"] = "ONY"
    stage_log["Ignition_Type"] = row.get("Ignition_Type", "NONE")
    
    return stage_log, "DIAMOND", "ONY", "V3_MATCH"

def run_simulation_v3():
    print("::: AVAX SIMULATOR V3 (FIXED: HARD CANCEL) :::")
    
    # Load Rules
    fail, succ, cancel, trig = load_v3_rules()
    
    # Load Data
    data_bundle = utils_io.get_data_bundle("AVAXUSDT")
    df_1d = avax_learn_core.calculate_technical_features(data_bundle['1d'], None, None, None)
    df_1d = core_indicators_v3.calculate_extended_indicators(df_1d)
    
    # Pre-calc Intraday Indicators
    print("Pre-calculating 4H/1H V3 Indicators...")
    df_4h = core_indicators_v3.calculate_extended_indicators(data_bundle['4h'])
    df_1h = core_indicators_v3.calculate_extended_indicators(data_bundle['1h'])
    
    # Labels
    df_1d = avax_learn_core.generate_labels(df_1d)
    
    # Test Split (Last 100)
    df_test = df_1d.iloc[-100:].copy()
    
    results = []
    logs = []
    
    for idx, row in df_test.iterrows():
        # Get Intraday Slices
        target_date = row['datetime'].date()
        
        # 4H Slice (Match Date)
        mask_4h = df_4h['datetime'].dt.date == target_date
        df_4h_day = df_4h[mask_4h]
        
        # 1H Slice
        mask_1h = df_1h['datetime'].dt.date == target_date
        df_1h_day = df_1h[mask_1h]
        
        # Eval
        log_entry, tier, verdict, reason = evaluate_day_v3(row, df_4h_day, df_1h_day, fail, succ, cancel, trig)
        logs.append(log_entry)
        
        v17_row = {}
        for col in v17_schema.V17_COLUMNS:
            if col == "Date": v17_row[col] = row['datetime'].isoformat()
            elif col == "Symbol": v17_row[col] = "AVAXUSDT"
            elif col == "Tier": v17_row[col] = tier
            elif col == "Audit_Verdict": v17_row[col] = verdict
            elif col in row: v17_row[col] = row[col]
            else: v17_row[col] = 0.0
            
        v17_row['Decision'] = log_entry['FinalDecision']
        v17_row['Reason'] = reason
        results.append(v17_row)
        
    df_res = pd.DataFrame(results)
    df_log = pd.DataFrame(logs)
    
    # Save Reports
    df_res[v17_schema.V17_COLUMNS].to_csv(REPORTS_DIR / "AVAX_V17_TEST_DAILY_V3_FIXED.csv", index=False)
    
    df_net = df_res[df_res['Decision'] == 'NET_ADAY']
    df_net[v17_schema.V17_COLUMNS].to_csv(REPORTS_DIR / "AVAX_NET_ADAY_REPORT_V3_FIXED.csv", index=False)
    
    df_log.to_csv(REPORTS_DIR / "AVAX_SIMULATION_STAGE_LOG.csv", index=False)
    
    # Performance
    acc = []
    for dec in ['NET_ADAY', 'WATCH', 'NO']:
        sub = df_res[df_res['Decision'] == dec]
        hits = len(sub[sub['Hit_10'] == 'YES'])
        count = len(sub)
        rate = hits/count*100 if count>0 else 0
        acc.append({"Decision": dec, "Count": count, "Hits": hits, "Hit_Rate": rate})
        
    df_perf = pd.DataFrame(acc)
    df_perf.to_csv(REPORTS_DIR / "AVAX_PERFORMANCE_SUMMARY_V3_FIXED.csv", index=False)
    
    print(df_perf)
    print(f"Fixed Reports saved to {REPORTS_DIR}")

if __name__ == "__main__":
    run_simulation_v3()
