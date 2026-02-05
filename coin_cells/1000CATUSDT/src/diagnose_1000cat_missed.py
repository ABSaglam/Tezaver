import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Paths
BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/1000CATUSDT/output/kader_v3_fixed/runs/run_001/reports")
LOG_FILE = BASE_DIR / "1000CATUSDT_SIMULATION_STAGE_LOG.csv"
V17_FILE = BASE_DIR / "1000CATUSDT_V17_TEST_DAILY.csv"

OUT_CSV = BASE_DIR / "1000CATUSDT_MISSED_DIAGNOSIS.csv"
OUT_MD = BASE_DIR / "1000CATUSDT_MISSED_VERDICT.md"

def diagnose():
    print("::: 1000CATUSDT MISSED DIAGNOSIS :::")
    
    # Load Logs
    if not LOG_FILE.exists() or not V17_FILE.exists():
        print(f"Error: Missing input files in {BASE_DIR}")
        return
        
    df_log = pd.read_csv(LOG_FILE)
    df_v17 = pd.read_csv(V17_FILE)
    
    # Merge
    # Ensure sorted
    df_log['Date'] = pd.to_datetime(df_log['Date'], utc=True)
    df_v17['Date'] = pd.to_datetime(df_v17['Date'], utc=True)
    
    df_log.sort_values('Date', inplace=True)
    df_v17.sort_values('Date', inplace=True)
    
    # Merge
    # We want metrics from V17 and decisions from LOG
    # V17 might have Decision but LOG has stage details
    df = pd.merge(df_log, df_v17, on='Date', suffixes=('_log', ''))
    
    # Missed Definition: Max48 >= 10.0 AND FinalDecision != 'NET_ADAY'
    missed_mask = (df['Max48'] >= 10.0) & (df['FinalDecision'] != 'NET_ADAY')
    df_missed = df[missed_mask].copy()
    
    print(f"Total Missed Days Found: {len(df_missed)}")
    
    diagnosis = []
    
    for idx, row in df_missed.iterrows():
        # Determine Stop Reason
        stop_stage = "UNKNOWN"
        stop_reason = "UNKNOWN"
        
        # Check based on LOG columns: DailyGate (bool), Cancel (bool)
        # Note: In 0GUSDT log file columns were 'DailyGate', 'Cancel'
        
        if not row['DailyGate']:
            stop_stage = "DAILY_GATE_FAIL"
            stop_reason = row.get('Reason', "Generic Gate Fail")
            if pd.isna(stop_reason): stop_reason = "Generic Gate Fail"
            
        elif row['Cancel']:
            stop_stage = "HARD_CANCEL"
            stop_reason = row['CancelReason']
            
        else:
            # Passed Daily, Not Canceled, but Decision NO/WATCH -> Trigger Fail
            stop_stage = "TRIGGER_NOT_CONFIRMED"
            stop_reason = "No Micro_Trig / Context"
            if "NO_TRIGGER" in str(row.get('Reason', '')):
                stop_reason = "NO_TRIGGER"
        
        diagnosis.append({
            "Date": row['Date'].isoformat(),
            "FinalDecision": row['FinalDecision'],
            "StopStage": stop_stage,
            "StopReason": stop_reason,
            "Score": row.get('Score', 0),
            "Energy_Gap": row.get('Energy_Gap', 0),
            "ADX": row.get('ADX', 0),
            "ATR_Norm": row.get('ATR_Norm', 0),
            "Vol_Ratio": row.get('Vol_Ratio', 0),
            "V-Mom": row.get('V-Mom', 0),
            "Wick_Ratio": row.get('Wick_Ratio', 0),
            "Dist_EMA": row.get('Dist_EMA', 0),
            "Anti_Penalty": row.get('Anti_Penalty', 0),
            "Drift_Factor": row.get('Drift_Factor', 0),
            "Hit_10": "YES"
        })
        
    df_diag = pd.DataFrame(diagnosis)
    df_diag.to_csv(OUT_CSV, index=False)
    
    # Generate Verdict MD
    if len(df_diag) > 0:
        counts = df_diag['StopStage'].value_counts()
        total = len(df_diag)
        
        md = "# 🩺 1000CATUSDT MISSED DIAGNOSIS REPORT\n\n"
        md += f"**Total Missed Opportunities:** {total}\n\n"
        
        md += "## Breakdown by Stop Stage\n"
        for stage, count in counts.items():
            md += f"- **{stage}:** {count} ({count/total*100:.1f}%)\n"
            
        # Top Reasons
        reasons = df_diag['StopReason'].value_counts().head(3)
        md += "\n## Top Rejection Reasons for Winners\n"
        for r, c in reasons.items():
            md += f"1. `{r}` ({c} days)\n"
            
        # Bottleneck Identification
        winner = counts.index[0]
        md += f"\n## ⚠️ MAIN BOTTLENECK: {winner}\n"
        if winner == "DAILY_GATE_FAIL":
            md += "Problem: **Fail Rules / Corridor** kuralları çok sıkı. Kazananlar baştan eleniyor.\n"
        elif winner == "HARD_CANCEL":
            md += "Problem: **Cancel Kuralları** (Wick/Ribbon) kazanan setupları 'False Positive' sanıp öldürüyor.\n"
        elif winner == "TRIGGER_NOT_CONFIRMED":
            md += "Problem: **Trigger (15M)** fazla hassas veya Daily-Gate geçse de teyit gelmiyor.\n"
            
    else:
        md = "# 🩺 1000CATUSDT DIAGNOSIS\nNo missed days found."
        
    with open(OUT_MD, "w") as f:
        f.write(md)
        
    print("Diagnosis complete.")
    if len(df_diag) > 0:
        print(df_diag[['Date', 'StopStage', 'StopReason']])

if __name__ == "__main__":
    diagnose()
