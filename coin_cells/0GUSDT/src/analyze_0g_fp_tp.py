import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Setup Paths
current_dir = Path(__file__).parent
sys.path.append(str(current_dir)) # coin_cells/0GUSDT/src
sys.path.append("/Users/alisaglam/TezaverMac")
sys.path.append("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/src")

import utils_io
import core_indicators_v3

BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/0GUSDT")
RUN_001 = BASE_DIR / "output/kader_v3_fixed/runs/run_001"
DATA_DIR = BASE_DIR / "data"
OUT_DIR = RUN_001 / "reports"

def load_targets():
    rep_path = RUN_001 / "reports/0GUSDT_NET_ADAY_REPORT.csv"
    if not rep_path.exists():
        print("Report not found")
        sys.exit(1)
        
    df = pd.read_csv(rep_path)
    # Filter only NET_ADAY just in case (report usually contains only them but header says so)
    # The file is literally 0GUSDT_NET_ADAY_REPORT, so it should be fine.
    
    df['Date'] = pd.to_datetime(df['Date'], utc=True).dt.date
    tp = df[df['Hit_10'] == 'YES']['Date'].tolist()
    fp = df[df['Hit_10'] == 'NO']['Date'].tolist()
    
    print(f"TP Dates: {tp}")
    print(f"FP Dates: {fp}")
    return tp, fp

def analyze_signatures(tp_dates, fp_dates):
    # Load Data using Utils or direct CSV since we know path
    # Utils handles parquet/csv logic better
    bundle = utils_io.get_data_bundle("0GUSDT")
    df4 = bundle['4h']
    df1 = bundle['1h']
    df15 = bundle['15m'] # Assuming this exists or loaded via utils? 
    # Utils get_data_bundle loads 1d, 4h, 1h. 15m usually load on demand.
    # Let's check if 15m is in bundle. Usually not.
    # Load 15m manually.
    f15 = DATA_DIR / "history_15m.parquet"
    if not f15.exists(): f15 = DATA_DIR / "0GUSDT_15m.csv"
    
    if str(f15).endswith("parquet"):
        df15 = pd.read_parquet(f15)
    else:
        df15 = pd.read_csv(f15)
        # Parse dates
        if 'timestamp' in df15.columns: # generic
             df15['datetime'] = pd.to_datetime(df15['timestamp'], unit='ms', utc=True)
        elif 'open_time' in df15.columns: # binance
             df15['datetime'] = pd.to_datetime(df15['open_time'], unit='ms', utc=True)
             
    # Calculate Core Indicators for 4H/1H (Ribbon, RSI)
    df4 = core_indicators_v3.calculate_extended_indicators(df4)
    df1 = core_indicators_v3.calculate_extended_indicators(df1)
    
    # Signatures
    sigs_4h1h = []
    sigs_15m = []
    
    all_dates = tp_dates + fp_dates
    
    for d in all_dates:
        is_tp = d in tp_dates
        role = "TP" if is_tp else "FP"
        
        # 4H Analysis
        sub4 = df4[df4['datetime'].dt.date == d]
        rib_in_4 = 0
        rsi_up_4 = 0
        rsi_dn_4 = 0
        brk_up_4 = 0
        wick_sum_4 = 0
        
        if len(sub4) > 0:
            rib_in_4 = len(sub4[sub4['STATE_RIBBON_INSIDE']==True]) / len(sub4)
            rsi_up_4 = len(sub4[sub4['RSI'] > sub4['RSI_EMA']]) / len(sub4) # Proxy for Lock Up if not calc
            # Actually core_indicators calculates RSI_LOCK_UP? No, internal to Learn.
            # core_indicators_v3 DOES calculate STATE_RSI_LOCK_UP if we use the right func.
            # calculate_extended_indicators adds STATE vars.
            rsi_up_4 = len(sub4[sub4['STATE_RSI_LOCK_UP']==True]) / len(sub4)
            rsi_dn_4 = len(sub4[sub4['STATE_RSI_LOCK_DN']==True]) / len(sub4)
            brk_up_4 = len(sub4[sub4['STATE_RIBBON_BREAK_UP']==True])
            
            # Wicks
            body_top = sub4[['open', 'close']].max(axis=1)
            hl = (sub4['high'] - sub4['low']).replace(0, np.nan)
            wicks = ((sub4['high'] - body_top) / hl).fillna(0)
            wick_sum_4 = wicks.mean()

        # 1H Analysis
        sub1 = df1[df1['datetime'].dt.date == d]
        rib_in_1 = 0
        rsi_up_1 = 0
        brk_up_1 = 0
        wick_sum_1 = 0
        
        if len(sub1) > 0:
            rib_in_1 = len(sub1[sub1['STATE_RIBBON_INSIDE']==True]) / len(sub1)
            rsi_up_1 = len(sub1[sub1['STATE_RSI_LOCK_UP']==True]) / len(sub1)
            brk_up_1 = len(sub1[sub1['STATE_RIBBON_BREAK_UP']==True])
            
            body_top = sub1[['open', 'close']].max(axis=1)
            hl = (sub1['high'] - sub1['low']).replace(0, np.nan)
            wicks = ((sub1['high'] - body_top) / hl).fillna(0)
            wick_sum_1 = wicks.mean()

        sigs_4h1h.append({
            "Date": d.isoformat(),
            "Role": role,
            "RibbonInside_4H": rib_in_4,
            "RSILockUp_4H": rsi_up_4,
            "RSILockDn_4H": rsi_dn_4,
            "BreakUpCount_4H": brk_up_4,
            "WickAvg_4H": wick_sum_4,
            "RibbonInside_1H": rib_in_1,
            "RSILockUp_1H": rsi_up_1,
            "WickAvg_1H": wick_sum_1
        })
        
        # 15M Analysis (Trigger Quality)
        sub15 = df15[df15['datetime'].dt.date == d].copy()
        trig_count = 0
        vol_peak = 0
        rsi_peak = 0
        
        if len(sub15) > 0 and 'volume' in sub15.columns:
             # Basic Trigger Approximation (V3 Trigger Logic is complex, we use key drivers)
             # V3 Trigger: Close > EMA21 + VolRatio > 1.5 + RSI > 55
             # Let's calc indicators
             sub15['EMA21'] = sub15['close'].ewm(span=21, adjust=False).mean()
             if 'RSI' not in sub15.columns: sub15['RSI'] = core_indicators_v3.calculate_rsi(sub15['close'])
             
             # Vol Ratio (Simple relative to mean of day? or just raw?)
             # Approximation: Vol / Mean Vol of Day
             mean_vol = sub15['volume'].mean()
             if mean_vol > 0:
                 sub15['VolRatio'] = sub15['volume'] / mean_vol
             else:
                 sub15['VolRatio'] = 0
                 
             vol_peak = sub15['VolRatio'].max()
             rsi_peak = sub15['RSI'].max()
             
             # Count potential triggers
             # Rule: Close > EMA21 and VolRatio > 2.0 and RSI > 50
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
        
    df_sig = pd.DataFrame(sigs_4h1h)
    df_sig.to_csv(OUT_DIR / "0GUSDT_FP_TP_4H1H_SIGNATURES.csv", index=False)
    
    df_15 = pd.DataFrame(sigs_15m)
    df_15.to_csv(OUT_DIR / "0GUSDT_FP_TP_15M_SIGNATURES.csv", index=False)
    
    return df_sig, df_15

def find_optimal_rule(df, df_15):
    best_rule = None
    best_filtered = 0 # Max is 3
    tp_safe = False
    
    print("::: SIGNATURES :::")
    print(df[['Date', 'Role', 'RibbonInside_4H', 'RSILockUp_4H', 'BreakUpCount_4H', 'WickAvg_4H', 'WickAvg_1H']])
    
    print("::: SIGNATURES 15M :::")
    print(df_15[['Date', 'Role', 'TriggerCount', 'VolPeak_15M', 'RSIPeak_15M']])
    
    # Strategy A: 4H Lock Gate (Existing)
    # IF RibbonInside_4H > X AND RSILockUp_4H < Y THEN CANCEL
    
    # Params
    x_vals = [0.5, 0.6, 0.7, 0.8, 0.9]
    y_vals = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    for x in x_vals:
        for y in y_vals:
            # Apply rule
            # Cancel if Inside > X AND Up < Y
            # TP must NOT cancel -> TP Input: Inside <= X OR Up >= Y
            
            tps = df[df['Role']=='TP']
            fps = df[df['Role']=='FP']
            
            # Check TP Safety
            # Safe if NOT (Inside > X and Up < Y)
            tp_ok = True
            for _, row in tps.iterrows():
                if row['RibbonInside_4H'] > x and row['RSILockUp_4H'] < y:
                    tp_ok = False
                    break
            
            if not tp_ok: continue
            
            # Check FP Kill
            fp_killed = 0
            for _, row in fps.iterrows():
                if row['RibbonInside_4H'] > x and row['RSILockUp_4H'] < y:
                    fp_killed += 1
            
            if fp_killed > best_filtered:
                best_filtered = fp_killed
                best_rule = f"IF RibbonInside_4H > {x} AND RSILockUp_4H < {y} THEN CANCEL"

def main():
    tp, fp = load_targets()
    df_sigs, df_15 = analyze_signatures(tp, fp)
    find_optimal_rule(df_sigs, df_15)

if __name__ == "__main__":
    main()
