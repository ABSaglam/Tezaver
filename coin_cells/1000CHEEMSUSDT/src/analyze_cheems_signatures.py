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

BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/1000CHEEMSUSDT")
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
    rep_path = RUN_001 / "reports/1000CHEEMSUSDT_NET_ADAY_REPORT.csv"
    if not rep_path.exists():
        print(f"Report not found: {rep_path}")
        sys.exit(1)
        
    df = pd.read_csv(rep_path)
    df['Date'] = pd.to_datetime(df['Date'], utc=True).dt.date
    tp = df[df['Hit_10'] == 'YES']['Date'].tolist()
    fp = df[df['Hit_10'] == 'NO']['Date'].tolist()
    return tp, fp

def analyze_cheems(tp_dates, fp_dates):
    # Load 15m
    f15 = DATA_DIR / "1000CHEEMSUSDT_15m.csv" 
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
        vol_peak = 0
        rsi_peak = 0
        
        if len(sub15) > 0 and 'volume' in sub15.columns:
             sub15['EMA21'] = sub15['close'].ewm(span=21, adjust=False).mean()
             if 'RSI' not in sub15.columns: sub15['RSI'] = calculate_rsi_internal(sub15['close'])
             mean_vol = sub15['volume'].mean()
             sub15['VolRatio'] = sub15['volume'] / mean_vol if mean_vol > 0 else 0
             
             vol_peak = sub15['VolRatio'].max()
             rsi_peak = sub15['RSI'].max()
             
             trigs = sub15[
                 (sub15['close'] > sub15['EMA21']) & 
                 (sub15['VolRatio'] > 2.0) & 
                 (sub15['RSI'] > 50)
             ]
             trig_count = len(trigs)
             
             if trig_count > 0:
                 times = trigs['datetime'].sort_values()
                 delta = times.iloc[-1] - times.iloc[0]
                 span = delta.total_seconds() / 3600.0
                 
                 hours = times.dt.hour
                 q_set = set()
                 for h in hours:
                     if 0 <= h < 6: q_set.add(1)
                     elif 6 <= h < 12: q_set.add(2)
                     elif 12 <= h < 18: q_set.add(3)
                     elif 18 <= h <= 24: q_set.add(4)
                 quarters = len(q_set)
                 
                 max_burst = 0
                 for t in times:
                     end_t = t + pd.Timedelta(hours=1)
                     c = len(times[(times >= t) & (times < end_t)])
                     if c > max_burst: max_burst = c
                 burstiness = max_burst
        
        sigs.append({
            "Date": d.isoformat(),
            "Role": role,
            "TriggerCount": trig_count,
            "Span": span,
            "Quarters": quarters,
            "Burst": burstiness,
            "VolPeak": vol_peak
        })
        
    df_sig = pd.DataFrame(sigs)
    print("::: CHEEMS SIGNATURES :::")
    print(df_sig)
    df_sig.to_csv(OUT_DIR / "1000CHEEMSUSDT_DETAILED_SIGNATURES.csv", index=False)

if __name__ == "__main__":
    tp, fp = load_targets()
    analyze_cheems(tp, fp)
