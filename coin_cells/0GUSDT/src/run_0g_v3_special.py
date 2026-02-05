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
# Import factory just for utility usage if needed, but we write custom logic
from coin_factory_v3_fixed import CoinFactory

BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/0GUSDT")
RUN_001 = BASE_DIR / "output/kader_v3_fixed/runs/run_001"
RUN_003 = BASE_DIR / "output/kader_v3_fixed/runs/run_003"

def get_missed_vals():
    # Reuse extraction logic
    v17_path = RUN_001 / "reports/0GUSDT_V17_TEST_DAILY.csv"
    diag_path = RUN_001 / "reports/0GUSDT_MISSED_DIAGNOSIS.csv"
    if not v17_path.exists() or not diag_path.exists(): return None
    
    df_v17 = pd.read_csv(v17_path)
    df_diag = pd.read_csv(diag_path)
    missed_dates = df_diag['Date'].tolist()
    
    # Normalize
    df_v17['Date'] = pd.to_datetime(df_v17['Date'], utc=True).apply(lambda x: x.isoformat())
    try: missed_dates = [pd.to_datetime(d).isoformat() for d in missed_dates]
    except: pass
    
    return df_v17[df_v17['Date'].isin(missed_dates)].copy()

def calc_v3_corridor():
    # Load Strict V1
    with open(RUN_001 / "rules/0gusdt_success_corridor.json") as f:
        strict_corr = json.load(f)
        
    df_missed = get_missed_vals()
    if df_missed is None or df_missed.empty:
        print("No missed data found")
        return strict_corr, strict_corr, []
        
    relax_corr = strict_corr.copy()
    meta_log = []
    
    # Wick Ratio Min
    wick_min_strict = strict_corr['Wick_Ratio']['min']
    wick_vals = df_missed['Wick_Ratio'].dropna()
    if len(wick_vals) > 0:
        wick_needed = wick_vals.min()
        # Rule: max(0.0, needed)
        # Note: actually strict_corr is P10 or P15? Original was P15-P85.
        wick_new = max(0.0, min(wick_min_strict, wick_needed))
        
        # Apply only if needed
        if wick_new < wick_min_strict:
            relax_corr['Wick_Ratio'] = strict_corr['Wick_Ratio'].copy()
            relax_corr['Wick_Ratio']['min'] = float(wick_new)
            meta_log.append(f"Wick_Ratio Min: {wick_min_strict:.4f} -> {wick_new:.4f}")

    # Dist EMA Min
    dist_min_strict = strict_corr['Dist_EMA']['min']
    dist_vals = df_missed['Dist_EMA'].dropna()
    if len(dist_vals) > 0:
        dist_needed = dist_vals.min()
        # Rule: limit = dist_min * 1.20 (more negative) if negative
        # If positive, shrinking? Assuming Dist Min is usually negative or close to 0.
        # Let's assume absolute expansion.
        limit = dist_min_strict - abs(dist_min_strict * 0.20)
        
        # dist_new = max(needed, limit)
        # If dist_needed is -0.15 and limit is -0.12 (from -0.10 strict), we take -0.12.
        # But wait, user said "en fazla %20 daha aşağı genişleyebilir".
        # So limited by limit.
        if dist_needed < dist_min_strict:
            dist_new = max(dist_needed, limit)
            relax_corr['Dist_EMA'] = strict_corr['Dist_EMA'].copy()
            relax_corr['Dist_EMA']['min'] = float(dist_new)
            meta_log.append(f"Dist_EMA Min: {dist_min_strict:.4f} -> {dist_new:.4f} (Limit: {limit:.4f}, Needed: {dist_needed:.4f})")
            
    return strict_corr, relax_corr, meta_log

def check_corridor(row, corr):
    for col, bands in corr.items():
        val = row.get(col)
        if val is not None:
            if val < bands['min'] or val > bands['max']:
                return False, col
    return True, None

def evaluate_day_tiered(row, fail, strict_corr, relax_corr, cancel, trig):
    reasons = []
    
    # 1. FAIL RULES (HARD VETO)
    for col, limits in fail.items():
        if col=="suppression_veto": continue
        val = row.get(col)
        if val:
            if val < limits.get('min_hard', -999): return "NO", "RED", "SILVER", f"{col}_LOW_VETO"
            if val > limits.get('max_hard', 999): return "NO", "RED", "SILVER", f"{col}_HIGH_VETO"
            
    if fail.get('suppression_veto', {}).get('active') and row.get('STATE_RIBBON_SUPPRESSION_UP'):
        return "NO", "RED", "SILVER", "SUPPRESSION_VETO"
        
    # 2. CORRIDOR (TIERED)
    # First check Relaxed (Wider)
    pass_relax, fail_col_relax = check_corridor(row, relax_corr)
    if not pass_relax:
        return "NO", "RED", "SILVER", f"{fail_col_relax}_OUT"
        
    # Passed Relaxed. Now Check Strict.
    pass_strict, fail_col_strict = check_corridor(row, strict_corr)
    
    tier = "GOLD" if not pass_strict else "DIAMOND"
    
    # 3. HARD CANCEL
    # Wick Check
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
        
    # 4. DECISION
    # If Tier is GOLD (Relaxed Only) -> Max WATCH
    if tier == "GOLD":
        return "WATCH", "RED", "GOLD", "RELAXED_CORRIDOR_ONLY"
        
    # If Tier is DIAMOND (Strict) -> Check Trigger -> NET_ADAY
    if row.get('Micro_Trig') == False and not (row.get('STATE_RSI_LOCK_UP') or row.get('STATE_RIBBON_BREAK_UP')):
        return "WATCH", "RED", "DIAMOND", "NO_TRIGGER"
        
    return "NET_ADAY", "ONY", "DIAMOND", "V3_MATCH"

def run_003():
    print("::: RUN 003: TIERED CORRIDOR (0GUSDT) :::")
    
    # Setup Output
    RUN_003.mkdir(parents=True, exist_ok=True)
    (RUN_003 / "rules").mkdir(exist_ok=True)
    (RUN_003 / "reports").mkdir(exist_ok=True)
    
    # Copy immutable rules
    for f in ["0gusdt_fail_rules.json", "0gusdt_intraday_cancel_rules.json", "0gusdt_trigger_map.json"]:
        shutil.copy(RUN_001 / "rules" / f, RUN_003 / "rules" / f)
        
    # Calc & Save V3 Corridor
    strict_corr, relax_corr, meta = calc_v3_corridor()
    utils_io.save_json_rule(relax_corr, RUN_003 / "rules/0gusdt_success_corridor_v3.json")
    
    (RUN_003 / "rules/meta").mkdir(parents=True, exist_ok=True)
    with open(RUN_003 / "rules/meta/corridor_relax_note.txt", "w") as f:
        f.write("\n".join(meta))
        
    # Load Data
    bundle = utils_io.get_data_bundle("0GUSDT")
    df = avax_learn_core.calculate_technical_features(bundle['1d'], None, None, None)
    df = core_indicators_v3.calculate_extended_indicators(df)
    df6 = avax_learn_core.generate_labels(df)
    
    df4h = core_indicators_v3.calculate_extended_indicators(bundle['4h'])
    df1h = core_indicators_v3.calculate_extended_indicators(bundle['1h'])
    
    # Load other rules
    with open(RUN_003 / "rules/0gusdt_fail_rules.json") as f: fail = json.load(f)
    with open(RUN_003 / "rules/0gusdt_intraday_cancel_rules.json") as f: cancel = json.load(f)
    with open(RUN_003 / "rules/0gusdt_trigger_map.json") as f: trig = json.load(f)
    
    # Simulate
    df_test = df6.iloc[-100:].copy()
    results = []
    logs = []
    
    for idx, row in df_test.iterrows():
        target_date = row['datetime'].date()
        df_4h_day = df4h[df4h['datetime'].dt.date == target_date]
        
        # Inject for eval access
        # Create a dict copy avoiding pandas SettingWithCopy warning on slice
        row_dict = row.to_dict()
        row_dict['_df_4h_day'] = df_4h_day
        
        dec, verd, tier, reason = evaluate_day_tiered(row_dict, fail, strict_corr, relax_corr, cancel, trig)
        
        # Log
        cancel_applied = "WICK" in reason or "RIBBON" in reason
        logs.append({
            "Date": row['datetime'].isoformat(),
            "FinalDecision": dec,
            "Tier": tier,
            "Reason": reason,
            "Cancel": cancel_applied,
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
    
    df_res[v17_schema.V17_COLUMNS].to_csv(RUN_003 / "reports/0GUSDT_V17_TEST_DAILY_RUN003.csv", index=False)
    df_res[df_res['Decision']=='NET_ADAY'][v17_schema.V17_COLUMNS].to_csv(RUN_003 / "reports/0GUSDT_NET_ADAY_REPORT_RUN003.csv", index=False)
    df_log.to_csv(RUN_003 / "reports/0GUSDT_SIMULATION_STAGE_LOG_RUN003.csv", index=False)
    
    # Generate Recheck MD
    missed_df = get_missed_vals()
    missed_dates = missed_df['Date'].tolist()
    
    md = "# 0GUSDT RUN 003 RECHECK\n\n"
    md += "Changes:\n" + "\n".join(meta) + "\n\n"
    
    md += "| Date | Run 001 | Run 003 Decision | Tier | Recovered? |\n|---|---|---|---|---|\n"
    rec_count = 0
    
    for d in missed_dates:
        r3 = df_res[df_res['Date']==d]
        if len(r3) > 0:
            dec = r3.iloc[0]['Decision']
            tier = r3.iloc[0]['Tier']
            # Recovered means NOT NO. Either WATCH (Gold) or NET_ADAY (Diamond)
            rec = "✅ YES" if dec in ["NET_ADAY", "WATCH"] else "❌ NO"
            if dec != "NO": rec_count += 1
            md += f"| {d[:10]} | NO | {dec} | {tier} | {rec} |\n"
            
    md += f"\n**Recovery Rate:** {rec_count}/{len(missed_dates)}\n"
    
    with open(RUN_003 / "reports/0GUSDT_MISSED_RECHECK_RUN003.md", "w") as f:
        f.write(md)
        
    print("Run 003 Complete.")

if __name__ == "__main__":
    run_003()
