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
import avax_kader_simulator_v3

BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/0GUSDT")
RUN_001 = BASE_DIR / "output/kader_v3_fixed/runs/run_001"
RUN_002 = BASE_DIR / "output/kader_v3_fixed/runs/run_002"
DATA_DIR = BASE_DIR / "data"

TRAIN_START = pd.Timestamp("2023-01-01", tz="UTC")
TRAIN_END = pd.Timestamp("2025-12-31", tz="UTC")

def get_missed_days_values():
    # Load V17 Daily from Run 001
    v17_path = RUN_001 / "reports/0GUSDT_V17_TEST_DAILY.csv"
    diag_path = RUN_001 / "reports/0GUSDT_MISSED_DIAGNOSIS.csv"
    
    if not v17_path.exists() or not diag_path.exists():
        print("Missing Run 001 files")
        return pd.DataFrame()
        
    df_v17 = pd.read_csv(v17_path)
    df_diag = pd.read_csv(diag_path)
    
    # Filter V17 for missed dates
    missed_dates = df_diag['Date'].tolist()
    # Ensure format match
    df_v17['Date'] = pd.to_datetime(df_v17['Date'], utc=True).apply(lambda x: x.isoformat())
    # Normalize diag dates if proper ISO
    try:
        missed_dates = [pd.to_datetime(d).isoformat() for d in missed_dates]
    except:
        pass
        
    df_vals = df_v17[df_v17['Date'].isin(missed_dates)].copy()
    return df_vals

def learn_v2_corridor(df_1d, df_missed):
    print("::: LEARNING V2 CORRIDOR (0GUSDT SPECIAL) :::")
    
    # Feature Gen
    df = avax_learn_core.calculate_technical_features(df_1d, None, None, None)
    df = core_indicators_v3.calculate_extended_indicators(df)
    df = avax_learn_core.generate_labels(df)
    
    # Train Split
    mask = (df['datetime'] >= TRAIN_START) & (df['datetime'] <= TRAIN_END)
    df_train = df[mask].copy()
    
    df_yes = df_train[df_train['Hit_10'] == 'YES']
    print(f"Training on {len(df_yes)} Hit Days.")
    
    # Initial P10-P90
    corridor = {}
    cols_to_learn = ['ATR_Norm', 'Energy_Gap', 'Wick_Ratio', 'Dist_EMA', 'Vol_Ratio', 'V-Mom']
    
    # Safe cols to widen
    safe_cols = ['ATR_Norm', 'Energy_Gap', 'Vol_Ratio', 'V-Mom']
    
    meta_log = []
    
    for col in cols_to_learn:
        p10 = df_yes[col].quantile(0.10)
        p90 = df_yes[col].quantile(0.90)
        
        # Check Missed Days
        for idx, row in df_missed.iterrows():
            val = row.get(col)
            if val is None: continue
            
            # Debug check
            if val < p10 or val > p90:
                print(f"DEBUG: {col} Outlier? Val={val:.4f} P10={p10:.4f} P90={p90:.4f}")
            
            # If outside P10-P90
            if val < p10:
                if col in safe_cols:
                    p05 = df_yes[col].quantile(0.05)
                    # User said: "Eğer bu band STILL missed’leri dışarıda bırakıyorsa... P05–P95’e genişlet"
                    # We try to accommodate val, bounded by P05? 
                    # Or just use P05 if val < P05?
                    # Let's take min(p10, max(val, p05)) -> Capture val but don't go below P05?
                    # No, if Val < P05 and we cap at P05, we still miss it. 
                    # User implies P05 is the limit. So we take P05.
                    # But if Val is -8.87 and P05 is -8.0, we miss it.
                    # Let's target P05 as the target.
                    if val < p05:
                        p10 = float(p05)
                        meta_log.append(f"Widened {col} Min to P05 ({p05:.4f}) [Val={val:.4f} was lower]")
                    else:
                        p10 = float(val)
                        meta_log.append(f"Widened {col} Min to {p10:.4f} to catch Missed Day.")
                else:
                    meta_log.append(f"Skipped widening {col} Min (Risk Col). Val={val:.4f} < P10={p10:.4f}")
                    
            if val > p90:
                if col in safe_cols:
                    p95 = df_yes[col].quantile(0.95)
                    if val > p95:
                         p90 = float(p95)
                         meta_log.append(f"Widened {col} Max to P95 ({p95:.4f}) [Val={val:.4f} was higher]")
                    else:
                         p90 = float(val)
                         meta_log.append(f"Widened {col} Max to {p90:.4f} to catch Missed Day.")
                else:
                    meta_log.append(f"Skipped widening {col} Max (Risk Col). Val={val:.4f} > P90={p90:.4f}")

        corridor[col] = {"min": float(p10), "max": float(p90)}
        
    # ADX Floor (V3 Standard)
    corridor['ADX'] = {"min": 35.0, "max": 100.0}
    
    # Score Min Check?
    # User: "Score min eşiği: 0GUSDT SUCCESS günlerinin p10’u alt sınır olsun."
    # 'Score' isn't usually in corridor dict but simulator checks it if present?
    # Actually simulator checks 'for col in corridor'. So adding 'Score' enforces it.
    if 'Score' in df_yes.columns:
        p10_score = df_yes['Score'].quantile(0.10)
        corridor['Score'] = {"min": float(p10_score), "max": 999.0}
        meta_log.append(f"Added Score Min Threshold: {p10_score}")
        
    return corridor, meta_log

def prepare_run_002(corridor_v2, meta_log):
    RUN_002.mkdir(parents=True, exist_ok=True)
    (RUN_002 / "rules").mkdir(exist_ok=True)
    (RUN_002 / "reports").mkdir(exist_ok=True)
    
    # Copy immutable rules
    for f_name in ["0gusdt_fail_rules.json", "0gusdt_intraday_cancel_rules.json", "0gusdt_trigger_map.json"]:
        src = RUN_001 / "rules" / f_name
        dst = RUN_002 / "rules" / f_name
        if src.exists():
            shutil.copy(src, dst)
            
    # Save V2 Corridor
    utils_io.save_json_rule(corridor_v2, RUN_002 / "rules/0gusdt_success_corridor_v2.json")
    # Rename to standard for loader? No, loader usually takes generic name unless specified.
    # Factory/Simulator usually takes `*_success_corridor.json`?
    # Let's save as `0gusdt_success_corridor.json` in run_002 to override.
    utils_io.save_json_rule(corridor_v2, RUN_002 / "rules/0gusdt_success_corridor.json")
    
    # Save Meta Log
    with open(RUN_002 / "rules/corridor_change_note.txt", "w") as f:
        f.write("\n".join(meta_log))
        
def run_simulation_002():
    # We can reuse similar logic to factory
    # But need to point to RUN_002
    
    # Manually invoke logic
    from coin_factory_v3_fixed import CoinFactory
    
    factory = CoinFactory("0GUSDT")
    # Override paths manually for this instance
    factory.out_path = RUN_002 # Redirect output to run_002
    factory.rules_path = RUN_002 / "rules"
    factory.reports_path = RUN_002 / "reports"
    
    # Load Data
    bundle = factory.load_data_bundle()
    
    # Load Rules from disk (since we prepared them)
    with open(factory.rules_path / "0gusdt_fail_rules.json") as f: fail = json.load(f)
    with open(factory.rules_path / "0gusdt_success_corridor.json") as f: succ = json.load(f)
    with open(factory.rules_path / "0gusdt_intraday_cancel_rules.json") as f: cancel = json.load(f)
    with open(factory.rules_path / "0gusdt_trigger_map.json") as f: trig = json.load(f)
    
    # Simulate
    # Need learned df. We can re-learn/calc or just calc since we have rules.
    # simulate expects df_learned (features).
    df_learned = avax_learn_core.calculate_technical_features(bundle['1d'], None, None, None)
    df_learned = core_indicators_v3.calculate_extended_indicators(df_learned)
    df_learned = avax_learn_core.generate_labels(df_learned)

    df_res, df_log = factory.simulate(df_learned, bundle['4h'], bundle['1h'], (fail, succ, cancel, trig))
    return df_res, df_log

def generate_comparison(df_res_v2):
    # Load V1 Missed
    df_missed_v1 = get_missed_days_values()
    df_res_v2['DateStr'] = pd.to_datetime(df_res_v2['Date']).apply(lambda x: x.isoformat())
    missed_dates = df_missed_v1['Date'].tolist()
    
    # Check status in V2
    md = "# 0GUSDT MISSED RECHECK (V2 CORRIDOR)\n\n"
    
    recovered_count = 0
    total_missed = len(missed_dates)
    
    md += f"**Original Missed Count:** {total_missed}\n\n"
    md += "| Date | V1 Decision | V2 Decision | Recovered? |\n"
    md += "|---|---|---|---|\n"
    
    for d in missed_dates:
        row_v2 = df_res_v2[df_res_v2['DateStr'] == d]
        if len(row_v2) > 0:
            dec_v2 = row_v2.iloc[0]['Decision']
            rec = "✅ YES" if dec_v2 == "NET_ADAY" else "❌ NO"
            if dec_v2 == "NET_ADAY": recovered_count += 1
            md += f"| {d[:10]} | NO/WATCH | {dec_v2} | {rec} |\n"
            
    md += f"\n**Recovery Rate:** {recovered_count}/{total_missed} ({recovered_count/total_missed*100:.1f}%)\n"
    
    # False Positive Check
    fp_v2 = len(df_res_v2[(df_res_v2['Decision']=='NET_ADAY') & (df_res_v2['Hit_10']=='NO')])
    md += f"\n**False Positives (V2):** {fp_v2} (Check performance summary for full details)."
    
    with open(RUN_002 / "reports/0GUSDT_MISSED_RECHECK.md", "w") as f:
        f.write(md)
        
    print("Recheck report generated.")

def main():
    bundle = utils_io.get_data_bundle("0GUSDT")
    df_missed = get_missed_days_values()
    
    if df_missed.empty:
        print("No missed days to refine.")
        return

    corridor_v2, meta = learn_v2_corridor(bundle['1d'], df_missed)
    prepare_run_002(corridor_v2, meta)
    
    df_res, df_log = run_simulation_002()
    # Rename reports for fixed convention
    # Factory saves as standard names. We rename them?
    # User requested: 0GUSDT_V17_TEST_DAILY_FIXED.csv etc.
    # Actually factory saves as `0GUSDT_V17_TEST_DAILY.csv` inside run_002.
    # User asked for `_FIXED.csv` in `run_002`.
    # I will rename them.
    
    rep_dir = RUN_002 / "reports"
    for f in rep_dir.glob("*.csv"):
        if "_FIXED" not in f.name:
            new_name = f.name.replace(".csv", "_FIXED.csv")
            shutil.move(f, rep_dir / new_name)
            
    generate_comparison(df_res)
    print("Run 002 Complete.")

if __name__ == "__main__":
    main()
