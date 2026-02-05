import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Setup Paths
current_dir = Path(__file__).parent
sys.path.append(str(current_dir)) 
sys.path.append("/Users/alisaglam/TezaverMac")
sys.path.append("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/src")

import utils_io
import core_indicators_v3

BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/1000CATUSDT")
RUN_001 = BASE_DIR / "output/kader_v3_fixed/runs/run_001"
DATA_DIR = BASE_DIR / "data"
OUT_DIR = RUN_001 / "reports"

def calculate_rsi_internal(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def load_targets():
    rep_path = RUN_001 / "reports/1000CATUSDT_NET_ADAY_REPORT.csv"
    if not rep_path.exists():
        print(f"Report not found: {rep_path}")
        sys.exit(1)
        
    df = pd.read_csv(rep_path)
    df['Date'] = pd.to_datetime(df['Date'], utc=True).dt.date
    tp = df[df['Hit_10'] == 'YES']['Date'].tolist()
    fp = df[df['Hit_10'] == 'NO']['Date'].tolist()
    
    print(f"TP Dates: {tp}")
    print(f"FP Dates: {fp}")
    return tp, fp

def analyze_signatures(tp_dates, fp_dates):
    # Load 15m
    f15 = DATA_DIR / "1000CATUSDT_15m.csv" 
    if not f15.exists():
        f15_pq = DATA_DIR / "history_15m.parquet"
        if f15_pq.exists():
            df15 = pd.read_parquet(f15_pq)
        else:
             print("15m data not found")
             sys.exit(1)
    else:
        df15 = pd.read_csv(f15)
        
    # Standardize datetime
    if 'timestamp' in df15.columns:
         df15['datetime'] = pd.to_datetime(df15['timestamp'], unit='ms', utc=True)
    elif 'open_time' in df15.columns:
         df15['datetime'] = pd.to_datetime(df15['open_time'], unit='ms', utc=True)
         
    sigs_15m = []
    all_dates = tp_dates + fp_dates
    
    for d in all_dates:
        is_tp = d in tp_dates
        role = "TP" if is_tp else "FP"
        
        sub15 = df15[df15['datetime'].dt.date == d].copy()
        trig_count = 0
        vol_peak = 0
        rsi_peak = 0
        
        if len(sub15) > 0 and 'volume' in sub15.columns:
             # Calculate indicators for Trigger Approx
             sub15['EMA21'] = sub15['close'].ewm(span=21, adjust=False).mean()
             if 'RSI' not in sub15.columns: 
                 sub15['RSI'] = calculate_rsi_internal(sub15['close'])
             
             mean_vol = sub15['volume'].mean()
             if mean_vol > 0:
                 sub15['VolRatio'] = sub15['volume'] / mean_vol
             else:
                 sub15['VolRatio'] = 0
                 
             vol_peak = sub15['VolRatio'].max()
             rsi_peak = sub15['RSI'].max()
             
             # Trigger Rule: Close > EMA21 & VolRatio > 2.0 & RSI > 50
             trigs = sub15[
                 (sub15['close'] > sub15['EMA21']) & 
                 (sub15['VolRatio'] > 2.0) & 
                 (sub15['RSI'] > 50)
             ]
             trig_count = len(trigs)
            
        sigs_15m.append({
            "Date": d.isoformat(),
            "Role": role,
            "CountBars_15M": len(sub15),
            "TriggerCount": trig_count,
            "VolPeak_15M": vol_peak,
            "RSIPeak_15M": rsi_peak
        })
        
    df_15 = pd.DataFrame(sigs_15m)
    df_15.to_csv(OUT_DIR / "1000CATUSDT_FP_TP_15M_SIGNATURES.csv", index=False)
    return df_15

def find_optimal_rule(df_15):
    print("::: SIGNATURES 15M :::")
    print(df_15[['Date', 'Role', 'TriggerCount', 'VolPeak_15M', 'RSIPeak_15M']])
    
    # Grid Search K
    best_rule = None
    best_filtered = 0
    
    tps = df_15[df_15['Role']=='TP']
    fps = df_15[df_15['Role']=='FP']
    
    # K range 3..12
    for k in range(3, 13):
        # TP Safety: TP must have >= K triggers
        tp_ok = True
        for _, row in tps.iterrows():
            if row['TriggerCount'] < k: tp_ok = False
            
        if tp_ok:
            fp_killed = 0
            for _, row in fps.iterrows():
                if row['TriggerCount'] < k: fp_killed += 1
            
            if fp_killed > best_filtered:
                best_filtered = fp_killed
                best_rule = f"IF 15M_TriggerCount < {k} THEN REJECT_TRIGGER"
                
    res = ""
    if best_rule:
        res = f"Best Rule: {best_rule}\n"
        res += f"TP Protected: YES\n"
        res += f"FP Eliminated: {best_filtered}/3\n"
        res += "Valid Layer: 15M_TRIGGER\n"
    else:
        res = "No optimal rule found in range [3..12].\n"
        
    print(res)
    with open(OUT_DIR / "1000CATUSDT_MINIMAL_FP_KILL_RULE.txt", "w") as f:
        f.write(res)
        
    # Sanity CSV
    sanity = []
    k_final = 0
    if best_rule:
        # Extract K
        k_final = int(best_rule.split('<')[1].split('THEN')[0].strip())
        
    for _, row in df_15.iterrows():
        role = row['Role']
        is_tp = (role == "TP")
        
        decision = "NET_ADAY"
        if best_rule and row['TriggerCount'] < k_final:
            decision = "NO"
            
        correct = (is_tp and decision=="NET_ADAY") or (not is_tp and decision=="NO")
        
        sanity.append({
            "Date": row['Date'],
            "WasTP": is_tp,
            "OldDecision": "NET_ADAY",
            "NewDecision": decision,
            "Correct": correct
        })
        
    pd.DataFrame(sanity).to_csv(OUT_DIR / "1000CATUSDT_FP_KILL_SANITY.csv", index=False)

def main():
    tp, fp = load_targets()
    df_15 = analyze_signatures(tp, fp)
    find_optimal_rule(df_15)

if __name__ == "__main__":
    main()
