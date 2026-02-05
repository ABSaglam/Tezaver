import pandas as pd
import numpy as np
import json
import sys
import shutil
from pathlib import Path

# Setup Paths
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
sys.path.append("/Users/alisaglam/TezaverMac")
sys.path.append("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/src")

import utils_io
import avax_learn_core
import core_indicators_v3
import v17_schema

BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/0GUSDT")
RUN_001 = BASE_DIR / "output/kader_v3_fixed/runs/run_001"
RUN_002 = BASE_DIR / "output/kader_v3_fixed/runs/run_002"
RUN_003 = BASE_DIR / "output/kader_v3_fixed/runs/run_003"
RUN_004 = BASE_DIR / "output/kader_v3_fixed/runs/run_004"

def get_missed_vals():
    v17_path = RUN_001 / "reports/0GUSDT_V17_TEST_DAILY.csv"
    diag_path = RUN_001 / "reports/0GUSDT_MISSED_DIAGNOSIS.csv"
    if not v17_path.exists() or not diag_path.exists(): return None
    
    df_v17 = pd.read_csv(v17_path)
    df_diag = pd.read_csv(diag_path)
    missed_dates = df_diag['Date'].tolist()
    
    df_v17['Date'] = pd.to_datetime(df_v17['Date'], utc=True).apply(lambda x: x.isoformat())
    try: missed_dates = [pd.to_datetime(d).isoformat() for d in missed_dates]
    except: pass
    
    return df_v17[df_v17['Date'].isin(missed_dates)].copy()

def merge_corridors():
    print("Merging V1, V2, V3...")
    with open(RUN_001 / "rules/0gusdt_success_corridor.json") as f: v1 = json.load(f)
    with open(RUN_002 / "rules/0gusdt_success_corridor_v2.json") as f: v2 = json.load(f)
    with open(RUN_003 / "rules/0gusdt_success_corridor_v3.json") as f: v3 = json.load(f)
    
    # Watch Bounds starts as V1
    watch = v1.copy()
    
    # Apply Safe from V2 (Energy, ATR, Vol, V-Mom)
    safe_cols = ['Energy_Gap', 'ATR_Norm', 'Vol_Ratio', 'V-Mom']
    for col in safe_cols:
        if col in v2:
            watch[col] = v2[col]
            
    # Apply Risk from V3 (Wick, Dist)
    risk_cols = ['Wick_Ratio', 'Dist_EMA']
    for col in risk_cols:
        if col in v3:
            watch[col] = v3[col]
            
    # Note in V4 object
    v4 = {
        "strict_bounds": v1,
        "watch_bounds": watch,
        "flags": {
            "watch_only": True,
            "allow_net_aday_from_watch": False
        }
    }
    return v4

def check_corridor(row, corr):
    for col, bands in corr.items():
        val = row.get(col)
        if val is not None:
            if val < bands['min'] or val > bands['max']:
                return False, col, val, bands['min'], bands['max']
    return True, None, 0,0,0

def evaluate_day_run004(row, fail, v4_rules, cancel, trig):
    strict_corr = v4_rules['strict_bounds']
    watch_corr = v4_rules['watch_bounds']
    
    # 1. FAIL RULES
    for col, limits in fail.items():
        if col=="suppression_veto": continue
        val = row.get(col)
        if val:
            if val < limits.get('min_hard', -999): return "NO", "RED", "SILVER", f"{col}_LOW_VETO"
            if val > limits.get('max_hard', 999): return "NO", "RED", "SILVER", f"{col}_HIGH_VETO"
            
    if fail.get('suppression_veto', {}).get('active') and row.get('STATE_RIBBON_SUPPRESSION_UP'):
        return "NO", "RED", "SILVER", "SUPPRESSION_VETO"
        
    # 2. WATCH CORRIDOR
    pass_watch, fail_col_w, val_w, min_w, max_w = check_corridor(row, watch_corr)
    if not pass_watch:
        # Log why failed watch
        limit = min_w if val_w < min_w else max_w
        return "NO", "RED", "SILVER", f"{fail_col_w}_OUT_WATCH (Val={val_w:.4f}, Limit={limit:.4f})"
        
    # 3. STRICT CORRIDOR
    pass_strict, fail_col_s, _, _, _ = check_corridor(row, strict_corr)
    
    tier = "GOLD" # Default passed Watch
    if pass_strict: tier = "DIAMOND"
    
    # 4. HARD CANCEL
    df_4h_day = row.get('_df_4h_day', pd.DataFrame())
    is_canceled = False
    cancel_why = ""
    
    if len(df_4h_day) > 0:
        body_top = df_4h_day[['open', 'close']].max(axis=1)
        hl = (df_4h_day['high'] - df_4h_day['low']).replace(0, np.nan)
        mean_wick = ((df_4h_day['high'] - body_top) / hl).fillna(0).mean()
        if mean_wick > cancel.get('wick_ratio_4h',{}).get('threshold', 0.28):
            is_canceled = True; cancel_why = f"WICK_4H ({mean_wick:.2f})"
            
    if not is_canceled and len(df_4h_day) > 0:
        cnt = len(df_4h_day[df_4h_day['STATE_RIBBON_SUPPRESSION_UP'] == True])
        if cnt/len(df_4h_day) >= 0.5:
            is_canceled = True; cancel_why = "RIBBON_TRAP"
            
    if is_canceled:
        return "NO", "RED", "SILVER", cancel_why
        
    # 5. DECISION
    if tier == "GOLD":
        return "WATCH", "RED", "GOLD", "WATCH_CORRIDOR_ONLY"
        
    # If DIAMOND -> Active
    if row.get('Micro_Trig') == False and not (row.get('STATE_RSI_LOCK_UP') or row.get('STATE_RIBBON_BREAK_UP')):
        return "WATCH", "RED", "DIAMOND", "NO_TRIGGER"
        
    return "NET_ADAY", "ONY", "DIAMOND", "V3_MATCH"

def run_004():
    print("::: RUN 004: UNION (0GUSDT) :::")
    
    RUN_004.mkdir(parents=True, exist_ok=True)
    (RUN_004 / "rules").mkdir(exist_ok=True)
    (RUN_004 / "reports").mkdir(exist_ok=True)
    
    # Copy immutables
    for f in ["0gusdt_fail_rules.json", "0gusdt_intraday_cancel_rules.json", "0gusdt_trigger_map.json"]:
        shutil.copy(RUN_001 / "rules" / f, RUN_004 / "rules" / f)
        
    # Merge V4
    v4 = merge_corridors()
    with open(RUN_004 / "rules/0gusdt_success_corridor_v4.json", "w") as f:
        json.dump(v4, f, indent=2)
        
    # Load Data
    bundle = utils_io.get_data_bundle("0GUSDT")
    df = avax_learn_core.calculate_technical_features(bundle['1d'], None, None, None)
    df = core_indicators_v3.calculate_extended_indicators(df)
    df6 = avax_learn_core.generate_labels(df)
    
    df4h = core_indicators_v3.calculate_extended_indicators(bundle['4h'])
    
    # Load Rules
    with open(RUN_004 / "rules/0gusdt_fail_rules.json") as f: fail = json.load(f)
    with open(RUN_004 / "rules/0gusdt_intraday_cancel_rules.json") as f: cancel = json.load(f)
    with open(RUN_004 / "rules/0gusdt_trigger_map.json") as f: trig = json.load(f)
    
    # Simulate
    df_test = df6.iloc[-100:].copy()
    results = []
    logs = []
    
    for idx, row in df_test.iterrows():
        target_date = row['datetime'].date()
        df_4h_day = df4h[df4h['datetime'].dt.date == target_date]
        
        row_dict = row.to_dict()
        row_dict['_df_4h_day'] = df_4h_day
        
        dec, verd, tier, reason = evaluate_day_run004(row_dict, fail, v4, cancel, trig)
        
        logs.append({
            "Date": row['datetime'].isoformat(),
            "FinalDecision": dec,
            "Tier": tier,
            "Reason": reason,
            "Hit_10": row['Hit_10']
        })
        
        res_row = {col: row.get(col, 0.0) for col in v17_schema.V17_COLUMNS}
        res_row['Date'] = row['datetime'].isoformat()
        res_row['Symbol'] = "0GUSDT"
        res_row['Tier'] = tier
        res_row['Audit_Verdict'] = verd
        res_row['Decision'] = dec
        res_row['Reason'] = reason
        results.append(res_row)
        
    df_res = pd.DataFrame(results)
    df_log = pd.DataFrame(logs)
    
    df_res[v17_schema.V17_COLUMNS].to_csv(RUN_004 / "reports/0GUSDT_V17_TEST_DAILY_RUN004.csv", index=False)
    df_res[df_res['Decision']=='NET_ADAY'][v17_schema.V17_COLUMNS].to_csv(RUN_004 / "reports/0GUSDT_NET_ADAY_REPORT_RUN004.csv", index=False)
    df_log.to_csv(RUN_004 / "reports/0GUSDT_SIMULATION_STAGE_LOG_RUN004.csv", index=False)
    
    # MISS CHECK
    missed_df = get_missed_vals()
    missed_dates = missed_df['Date'].tolist()
    
    md = "# 0GUSDT RUN 004 MISSED RECHECK (UNION)\n\n"
    md += "| Date | Run 001 | Run 004 Decision | Tier | Recovered? | Stop Reason |\n|---|---|---|---|---|---|\n"
    
    rec_cnt = 0
    for d in missed_dates:
        r4 = df_res[df_res['Date']==d]
        stop = "N/A"
        dec = "N/A"
        tier = "N/A"
        
        if len(r4) > 0:
            dec = r4.iloc[0]['Decision']
            tier = r4.iloc[0]['Tier']
            stop = r4.iloc[0]['Reason']
            
        rec = "✅ YES" if dec in ["NET_ADAY", "WATCH"] else "❌ NO"
        if dec != "NO": rec_cnt += 1
        
        md += f"| {d[:10]} | NO | {dec} | {tier} | {rec} | {stop} |\n"
        
    md += f"\n**Recovery Rate:** {rec_cnt}/{len(missed_dates)}\n"
    
    with open(RUN_004 / "reports/0GUSDT_MISSED_RECHECK_RUN004.md", "w") as f:
        f.write(md)
        
    print("Run 004 Complete.")

if __name__ == "__main__":
    run_004()
