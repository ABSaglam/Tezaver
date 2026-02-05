import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Paths
BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT")
REPORTS_DIR = BASE_DIR / "output/avax_kader_v1/runs/initial_learn/reports"
DATA_DIR = BASE_DIR / "data"

# Dates
FAIL_DATE = "2025-11-30"
SUCCESS_DATE = "2025-12-02"

# Thresholds to sweep
THRESHOLDS = np.arange(0.27, 0.325, 0.005)

def calculate_wick_1h(df):
    # (High - max(Open, Close)) / (High - Low)
    body_top = df[['open', 'close']].max(axis=1)
    hl_range = df['high'] - df['low']
    # Avoid div/0
    hl_range = hl_range.replace(0, np.nan) 
    
    wick = (df['high'] - body_top) / hl_range
    return wick.fillna(0)

def analyze_day(df, date_str):
    # Filter by date
    # df indexed by datetime? or col?
    # Assuming df has datetime col
    target = pd.to_datetime(date_str).date()
    mask = df['datetime'].dt.date == target
    day_df = df[mask].copy()
    
    if len(day_df) == 0:
        return None
        
    wick = calculate_wick_1h(day_df)
    
    return {
        "Date": date_str,
        "Wick_Ratio_1h_avg": wick.mean(),
        "Wick_Ratio_1h_p75": wick.quantile(0.75),
        "Wick_Ratio_1h_max": wick.max()
    }

def run_analysis():
    print("::: 1H WICK ROBUSTNESS TEST :::")
    
    # 1. Load Data
    # prioritizing parquet as per known state
    fpath = DATA_DIR / "history_1h.parquet"
    if not fpath.exists():
        fpath = DATA_DIR / "AVAXUSDT_1h.csv" # Input request mentioned this
        
    if str(fpath).endswith('.parquet'):
        df = pd.read_parquet(fpath)
    else:
        df = pd.read_csv(fpath)
        
    # Standardize time
    if 'timestamp' in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    elif 'date' in df.columns:
        df['datetime'] = pd.to_datetime(df['date'], utc=True)
    
    # 2. Extract Signatures
    fail_sig = analyze_day(df, FAIL_DATE)
    success_sig = analyze_day(df, SUCCESS_DATE)
    
    if not fail_sig or not success_sig:
        print("Error: Could not find data for target dates.")
        return

    # 3. Save Signature CSV
    sigs = pd.DataFrame([fail_sig, success_sig])
    sigs.to_csv(REPORTS_DIR / "AVAX_WICK_1H_SIGNATURE_FAIL_SUCCESS.csv", index=False)
    print("Signatures:\n", sigs)
    
    # 4. Threshold Sweep
    results = []
    
    rule_types = ['Wick_Ratio_1h_avg', 'Wick_Ratio_1h_p75', 'Wick_Ratio_1h_max']
    
    valid_rules = []

    for r_type in rule_types:
        f_val = fail_sig[r_type]
        s_val = success_sig[r_type]
        
        for thr in THRESHOLDS:
            # Rule: IF val > thr THEN CANCEL
            cancel_fail = (f_val > thr)
            cancel_succ = (s_val > thr)
            
            passes_sanity = (cancel_fail == True) and (cancel_succ == False)
            
            res = {
                "RuleType": r_type,
                "THR": round(thr, 3),
                "FailCancels": cancel_fail,
                "SuccessCancels": cancel_succ,
                "PassesSanity": passes_sanity,
                "Margin": thr - s_val # How much room above success?
            }
            results.append(res)
            
            if passes_sanity:
                valid_rules.append(res)
                
    pd.DataFrame(results).to_csv(REPORTS_DIR / "AVAX_WICK_THRESHOLD_SWEEP_1H.csv", index=False)
    
    # 5. Select Best Rule
    # "Öncelik: avg > p75 > max"
    # "Success gününden en az 0.005 yukarı (margin)"
    
    best = None
    
    # Filter by margin > 0.005
    candidates = [r for r in valid_rules if r['Margin'] >= 0.005]
    
    if not candidates:
        print("NO_STABLE_1H_RULE_FOUND")
        with open(REPORTS_DIR / "AVAX_MINIMAL_CANCEL_RULE_1H.txt", "w") as f:
            f.write("NO_STABLE_1H_RULE_FOUND")
    else:
        # Sort by Type Priority (Avg=0, P75=1, Max=2) then by THR (lowest first)
        type_priority = {'Wick_Ratio_1h_avg': 0, 'Wick_Ratio_1h_p75': 1, 'Wick_Ratio_1h_max': 2}
        
        candidates.sort(key=lambda x: (type_priority[x['RuleType']], x['THR']))
        
        best = candidates[0]
        rule_str = f"IF {best['RuleType']} > {best['THR']} THEN CANCEL"
        
        print(f"\n>>> SELECTED 1H RULE: {rule_str}")
        print(f"Fail Val: {fail_sig[best['RuleType']]}, Success Val: {success_sig[best['RuleType']]}")
        
        with open(REPORTS_DIR / "AVAX_MINIMAL_CANCEL_RULE_1H.txt", "w") as f:
            f.write(rule_str)

if __name__ == "__main__":
    run_analysis()
