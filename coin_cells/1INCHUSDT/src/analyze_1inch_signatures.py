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

BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/1INCHUSDT")
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
    rep_path = RUN_001 / "reports/1INCHUSDT_NET_ADAY_REPORT.csv"
    if not rep_path.exists():
        print(f"Report not found: {rep_path}")
        sys.exit(1)
        
    df = pd.read_csv(rep_path)
    df['Date'] = pd.to_datetime(df['Date'], utc=True).dt.date
    tp = df[df['Hit_10'] == 'YES']['Date'].tolist()
    fp = df[df['Hit_10'] == 'NO']['Date'].tolist()
    return tp, fp

def analyze_1inch(tp_dates, fp_dates):
    # Load 15m
    f15 = DATA_DIR / "1INCHUSDT_15m.csv" 
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
        burstiness = 0
        vol_peak = 0
        avg_ft2 = 0
        
        if len(sub15) > 0 and 'volume' in sub15.columns:
             sub15['EMA21'] = sub15['close'].ewm(span=21, adjust=False).mean()
             if 'RSI' not in sub15.columns: sub15['RSI'] = calculate_rsi_internal(sub15['close'])
             mean_vol = sub15['volume'].mean()
             sub15['VolRatio'] = sub15['volume'] / mean_vol if mean_vol > 0 else 0
             
             vol_peak = sub15['VolRatio'].max()
             
             trigs = sub15[
                 (sub15['close'] > sub15['EMA21']) & 
                 (sub15['VolRatio'] > 2.0) & 
                 (sub15['RSI'] > 50)
             ]
             trig_count = len(trigs)
             
             ft_values = []
             if trig_count > 0:
                 times = trigs['datetime'].sort_values()
                 max_burst = 0
                 for t in times:
                     end_t = t + pd.Timedelta(hours=1)
                     c = len(times[(times >= t) & (times < end_t)])
                     if c > max_burst: max_burst = c
                     
                     # FollowThrough2: (Close[t+2] - Close[t]) / Close[t]
                     # Find index in sub15
                     idx_list = sub15.index[sub15['datetime'] == t].tolist()
                     if idx_list:
                         idx = idx_list[0]
                         # Check if idx+2 exists in df15 (might handle boundaries better if we use df15)
                         # But sub15 is slice. Let's use df15 for lookahead.
                         base_idx = df15.index[df15['datetime'] == t].tolist()[0]
                         if base_idx + 2 < len(df15):
                             c0 = df15.at[base_idx, 'close']
                             c2 = df15.at[base_idx+2, 'close']
                             pct = (c2 - c0) / c0 * 100
                             ft_values.append(pct)
                             
                 burstiness = max_burst
                 if ft_values:
                     avg_ft2 = np.mean(ft_values)
        
        sigs.append({
            "Date": d.isoformat(),
            "Role": role,
            "Count": trig_count,
            "Burst": burstiness,
            "VolPeak": vol_peak,
            "FT2_Avg": avg_ft2
        })
        
    df_sig = pd.DataFrame(sigs)
    print("::: 1INCH SIGNATURES :::")
    print(df_sig)
    df_sig.to_csv(OUT_DIR / "1INCHUSDT_FP_TP_15M_SIGNATURES.csv", index=False)
    return df_sig

def find_optimal_rule(df):
    tps = df[df['Role']=='TP']
    fps = df[df['Role']=='FP']
    
    print("\n::: SEARCHING RULES :::")
    best_rule = None
    best_score = -1 
    best_margin = 0
    
    # 1. Count Gate: >= K
    for k in range(4, 17):
        tp_pass = True
        for _, r in tps.iterrows():
            if r['Count'] < k: tp_pass = False
        
        if tp_pass:
            fp_killed = 0
            for _, r in fps.iterrows():
                if r['Count'] < k: fp_killed += 1
            
            if fp_killed > best_score:
                best_score = fp_killed
                best_rule = f"IF Count >= {k} THEN ACCEPT else REJECT"
                
    # 2. VolPeak Gate: >= V
    for v in np.arange(3.0, 15.0, 0.1):
        tp_pass = True
        for _, r in tps.iterrows():
            if r['VolPeak'] < v: tp_pass = False
        
        if tp_pass:
            fp_killed = 0
            for _, r in fps.iterrows():
                if r['VolPeak'] < v: fp_killed += 1
                
            if fp_killed > best_score: 
                best_score = fp_killed
                best_rule = f"IF VolPeak >= {v:.2f} THEN ACCEPT else REJECT"
                
    # 3. FollowThrough2 Gate: >= F
    for f in np.arange(0.0, 2.0, 0.1):
        tp_pass = True
        for _, r in tps.iterrows():
            if r['FT2_Avg'] < f: tp_pass = False
        
        if tp_pass:
            fp_killed = 0
            for _, r in fps.iterrows():
                if r['FT2_Avg'] < f: fp_killed += 1
            
            if fp_killed > best_score:
                best_score = fp_killed
                best_rule = f"IF FT2_Avg >= {f:.2f}% THEN ACCEPT else REJECT"

    # Save
    res = f"Best Rule: {best_rule}\nFP Killed: {best_score}/3\n"
    print(res)
    with open(OUT_DIR / "1INCHUSDT_MINIMAL_FP_KILL_RULE.txt", "w") as f:
        f.write(res)

if __name__ == "__main__":
    tp, fp = load_targets()
    df = analyze_1inch(tp, fp)
    find_optimal_rule(df)
