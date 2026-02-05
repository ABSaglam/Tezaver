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
    return tp, fp

def analyze_persistency(tp_dates, fp_dates):
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
        
    if 'timestamp' in df15.columns:
         df15['datetime'] = pd.to_datetime(df15['timestamp'], unit='ms', utc=True)
    elif 'open_time' in df15.columns:
         df15['datetime'] = pd.to_datetime(df15['open_time'], unit='ms', utc=True)
    
    sigs = []
    all_dates = tp_dates + fp_dates
    
    for d in all_dates:
        is_tp = d in tp_dates
        role = "TP" if is_tp else "FP"
        
        sub15 = df15[df15['datetime'].dt.date == d].copy()
        
        trig_count = 0
        span = 0
        quarters = 0
        burstiness = 0
        
        if len(sub15) > 0 and 'volume' in sub15.columns:
             # Calculate indicators
             sub15['EMA21'] = sub15['close'].ewm(span=21, adjust=False).mean()
             if 'RSI' not in sub15.columns: 
                 sub15['RSI'] = calculate_rsi_internal(sub15['close'])
             
             mean_vol = sub15['volume'].mean()
             sub15['VolRatio'] = sub15['volume'] / mean_vol if mean_vol > 0 else 0
             
             # Identify Triggers
             trigs = sub15[
                 (sub15['close'] > sub15['EMA21']) & 
                 (sub15['VolRatio'] > 2.0) & 
                 (sub15['RSI'] > 50)
             ]
             trig_count = len(trigs)
             
             if trig_count > 0:
                 # Span
                 times = trigs['datetime'].sort_values()
                 delta = times.iloc[-1] - times.iloc[0]
                 span = delta.total_seconds() / 3600.0
                 
                 # Quarters
                 hours = times.dt.hour
                 q_set = set()
                 for h in hours:
                     if 0 <= h < 6: q_set.add(1)
                     elif 6 <= h < 12: q_set.add(2)
                     elif 12 <= h < 18: q_set.add(3)
                     elif 18 <= h <= 24: q_set.add(4)
                 quarters = len(q_set)
                 
                 # Burstiness (Max trigs in 1h window)
                 # We iterate over trigs and count how many fall within [t, t+1h]
                 max_burst = 0
                 for t in times:
                     end_t = t + pd.Timedelta(hours=1)
                     count_in_window = len(times[(times >= t) & (times < end_t)])
                     if count_in_window > max_burst: max_burst = count_in_window
                 burstiness = max_burst
        
        sigs.append({
            "Date": d.isoformat(),
            "WasTP": is_tp,
            "Role": role,
            "TriggerCount": trig_count,
            "TriggerSpanHours": span,
            "ActiveQuarters": quarters,
            "Burstiness": burstiness
        })
        
    df_sig = pd.DataFrame(sigs)
    df_sig.to_csv(OUT_DIR / "1000CATUSDT_TRIGGER_PERSISTENCY_SIGNATURES.csv", index=False)
    return df_sig

def find_optimal_rule(df):
    print("::: PERSISTENCY SIGNATURES :::")
    print(df[['Date', 'Role', 'TriggerCount', 'TriggerSpanHours', 'ActiveQuarters', 'Burstiness']])
    
    tps = df[df['Role']=='TP']
    fps = df[df['Role']=='FP']
    
    best_rule = None
    best_filtered = 0
    tp_safe_final = False
    
    # Grid Search
    # A: Span. Params: X in [3,4,5,6,8]
    # Rule: IF TriggerCount >= 9 AND Span >= X THEN ACCEPT else REJECT
    # Equivalent to REJECT IF (TriggerCount >= 9 AND Span < X) OR (TriggerCount < 9)?
    # No, user wants base: "IF TriggerCount >= 9 ...". But user also wants to reject low counts (4, 3).
    # So implicitly: REJECT IF TriggerCount < 9 OR (TriggerCount >=9 AND Span < X).
    
    # Let's frame it as ACCEPTANCE rule.
    # TP must PASS. FPs must FAIL.
    
    # Strategy A: Span
    for x in [3, 4, 5, 6, 8]:
        # Condition to Pass: Count >= 9 AND Span >= X
        
        # Check TP
        tp_ok = True
        for _, r in tps.iterrows():
            if not (r['TriggerCount'] >= 9 and r['TriggerSpanHours'] >= x):
                tp_ok = False
        
        if tp_ok:
            fp_killed = 0
            for _, r in fps.iterrows():
                # FP passes if: Count >= 9 AND Span >= X
                # If NOT passed, it's killed.
                if not (r['TriggerCount'] >= 9 and r['TriggerSpanHours'] >= x):
                    fp_killed += 1
            
            if fp_killed > best_filtered:
                best_filtered = fp_killed
                best_rule = f"IF TriggerCount >= 9 AND TriggerSpanHours >= {x} THEN ACCEPT else REJECT"

    # Strategy B: Quarters
    for q in [2, 3, 4]:
        tp_ok = True
        for _, r in tps.iterrows():
            if not (r['TriggerCount'] >= 9 and r['ActiveQuarters'] >= q): tp_ok = False
            
        if tp_ok:
            fp_killed = 0
            for _, r in fps.iterrows():
                if not (r['TriggerCount'] >= 9 and r['ActiveQuarters'] >= q): fp_killed += 1
            
            if fp_killed > best_filtered: # prioritize if better
                best_filtered = fp_killed
                best_rule = f"IF TriggerCount >= 9 AND ActiveQuarters >= {q} THEN ACCEPT else REJECT"
                
    # Strategy C: Sensitivity/Burstiness
    # IF TriggerCount >= 9 AND Burstiness <= B THEN ACCEPT
    for b in [3, 4, 5, 6]:
         tp_ok = True
         for _, r in tps.iterrows():
             if not (r['TriggerCount'] >= 9 and r['Burstiness'] <= b): tp_ok = False
             
         if tp_ok:
             fp_killed = 0
             for _, r in fps.iterrows():
                 if not (r['TriggerCount'] >= 9 and r['Burstiness'] <= b): fp_killed += 1
             
             # If ties, maybe burstiness is less preferred? 
             if fp_killed > best_filtered:
                  best_filtered = fp_killed
                  best_rule = f"IF TriggerCount >= 9 AND Burstiness <= {b} THEN ACCEPT else REJECT"

    # Save
    res = ""
    if best_rule:
        res = f"Best Rule: {best_rule}\n"
        res += f"TP Protected: YES\n"
        res += f"FP Eliminated: {best_filtered}/3\n"
        res += "Valid Layer: 15M_TRIGGER_PERSISTENCY\n"
    else:
        res = "No optimal persistency rule found.\n"
        
    print(res)
    with open(OUT_DIR / "1000CATUSDT_MINIMAL_PERSISTENCY_RULE.txt", "w") as f:
        f.write(res)
        
    # Sanity
    sanity = []
    for _, row in df.iterrows():
        decision = "NET_ADAY" # Start as acceptable (assuming passed base filters)
        
        # Apply Rule Logic
        accepted = False
        if best_rule:
             # Parse
             # Ex: IF TriggerCount >= 9 AND TriggerSpanHours >= 6 THEN ACCEPT else REJECT
             cond_part = best_rule.split("THEN")[0].replace("IF ", "")
             # Check conditions
             pass_cond = True
             
             # Simple parsing
             count_ok = row['TriggerCount'] >= 9
             quality_ok = True
             
             if "TriggerSpanHours >=" in cond_part:
                 val = float(cond_part.split(">=")[2].strip())
                 if row['TriggerSpanHours'] < val: quality_ok = False
             elif "ActiveQuarters >=" in cond_part:
                 val = int(cond_part.split(">=")[2].strip())
                 if row['ActiveQuarters'] < val: quality_ok = False
             elif "Burstiness <=" in cond_part:
                 val = int(cond_part.split("<=")[1].strip())
                 if row['Burstiness'] > val: quality_ok = False
                 
             if count_ok and quality_ok:
                 accepted = True
             else:
                 accepted = False
        else:
            accepted = True # No rule, keep logic ?? No, implied rejected if no rule found?
        
        final_dec = "NET_ADAY" if accepted else "NO"
        is_tp = (row['Role'] == 'TP')
        correct = (is_tp and final_dec=="NET_ADAY") or (not is_tp and final_dec=="NO")
        
        sanity.append({
            "Date": row['Date'],
            "WasTP": is_tp,
            "OldDecision": "NET_ADAY",
            "NewDecision": final_dec,
            "Correct": correct
        })
        
    pd.DataFrame(sanity).to_csv(OUT_DIR / "1000CATUSDT_PERSISTENCY_SANITY.csv", index=False)

def main():
    tp, fp = load_targets()
    df_sig = analyze_persistency(tp, fp)
    find_optimal_rule(df_sig)

if __name__ == "__main__":
    main()
