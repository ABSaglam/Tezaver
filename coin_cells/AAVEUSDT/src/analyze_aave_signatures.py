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

BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/AAVEUSDT")
RUN_001 = BASE_DIR / "output/kader_v3_fixed/runs/run_001"
DATA_DIR = BASE_DIR / "data"
OUT_DIR = RUN_001 / "reports"

TP_DATE = pd.to_datetime("2025-12-02").date()
FP_DATES = [pd.to_datetime(d).date() for d in ["2025-11-07", "2025-11-25", "2025-12-05"]]

def calculate_rsi_internal(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_15m_signatures():
    # Load 15m
    f15 = DATA_DIR / "history_15m.parquet"
    if not f15.exists():
        f15 = DATA_DIR / "AAVEUSDT_15m.csv"
        if not f15.exists(): return None
        df15 = pd.read_csv(f15)
    else:
        df15 = pd.read_parquet(f15)
        
    if 'timestamp' in df15.columns:
         df15['datetime'] = pd.to_datetime(df15['timestamp'], unit='ms', utc=True)
    elif 'open_time' in df15.columns:
         df15['datetime'] = pd.to_datetime(df15['open_time'], unit='ms', utc=True)
    
    sigs = []
    all_dates = [TP_DATE] + FP_DATES
    
    for d in all_dates:
        role = "TP" if d == TP_DATE else "FP"
        sub15 = df15[df15['datetime'].dt.date == d].copy()
        
        trig_count = 0
        burstiness = 0
        vol_peak = 0
        avg_ft2 = 0
        quarters = 0
        rsi_lock_bars = 0
        
        if len(sub15) > 0 and 'volume' in sub15.columns:
             sub15['EMA21'] = sub15['close'].ewm(span=21, adjust=False).mean()
             if 'RSI' not in sub15.columns: sub15['RSI'] = calculate_rsi_internal(sub15['close'])
             sub15['RSI_EMA'] = sub15['RSI'].ewm(span=14, adjust=False).mean()
             
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
                 
                 # Quarters
                 hours = times.dt.hour
                 q_bins = [0,0,0,0]
                 for h in hours:
                     if h < 6: q_bins[0]=1
                     elif h < 12: q_bins[1]=1
                     elif h < 18: q_bins[2]=1
                     else: q_bins[3]=1
                 quarters = sum(q_bins)

                 for t in times:
                     end_t = t + pd.Timedelta(hours=1)
                     c = len(times[(times >= t) & (times < end_t)])
                     if c > max_burst: max_burst = c
                     
                     # FT2
                     mask = sub15['datetime'] == t
                     if mask.any():
                         c_idx = sub15.index[mask][0]
                         # Find t+30m if within slice
                         # Or just check next 2 rows if contiguous
                         # Safe generic lookup:
                         next_t = t + pd.Timedelta(minutes=30)
                         mask_next = sub15['datetime'] == next_t
                         if mask_next.any():
                             c2 = sub15.loc[mask_next, 'close'].values[0]
                             c0 = sub15.loc[mask, 'close'].values[0]
                             ft_values.append( (c2-c0)/c0*100 )

                 burstiness = max_burst
                 if ft_values: avg_ft2 = np.mean(ft_values)
                 
                 # RSI Lock Duration (Post first trigger)
                 first_t = times.iloc[0]
                 post_sub = sub15[sub15['datetime'] >= first_t]
                 # Count consecutive bars where RSI > RSI_EMA
                 # Simplified: total bars RSI > RSI_EMA in post trigger session
                 rsi_lock_bars = len(post_sub[post_sub['RSI'] > post_sub['RSI_EMA']])

        sigs.append({
            "Date": d.isoformat(),
            "Role": role,
            "Count": trig_count,
            "Burst": burstiness,
            "VolPeak": vol_peak,
            "FT2_Avg": avg_ft2,
            "Quarters": quarters,
            "RSILock": rsi_lock_bars
        })
        
    return pd.DataFrame(sigs)

def get_4h_regime():
    f4h = DATA_DIR / "history_4h.parquet"
    if not f4h.exists():
        f4h = DATA_DIR / "AAVEUSDT_4h.csv"
        if not f4h.exists(): return None
        df4h = pd.read_csv(f4h)
    else:
        df4h = pd.read_parquet(f4h)

    if 'timestamp' in df4h.columns:
         df4h['datetime'] = pd.to_datetime(df4h['timestamp'], unit='ms', utc=True)
    elif 'open_time' in df4h.columns:
         df4h['datetime'] = pd.to_datetime(df4h['open_time'], unit='ms', utc=True)
         
    # Calc indicators
    df4h = core_indicators_v3.calculate_extended_indicators(df4h)

    regimes = []
    all_dates = [TP_DATE] + FP_DATES
    
    for d in all_dates:
        role = "TP" if d == TP_DATE else "FP"
        # Get candles for that day
        day_candles = df4h[df4h['datetime'].dt.date == d]
        
        ribbon_state = "UNKNOWN"
        # Check median state
        if len(day_candles) > 0:
            if day_candles['STATE_RIBBON_BREAK_UP'].any(): ribbon_state = "BREAK_UP"
            elif day_candles['STATE_RIBBON_SUPPRESSION_UP'].any(): ribbon_state = "SUPPRESSION_UP" # Usually mapped to Inside/Break logic
            else: ribbon_state = "NORMAL"
            
        trend_higher_low = False
        # Simple check: Day Close > Day Open
        if len(day_candles) > 0:
            day_open = day_candles.iloc[0]['open']
            day_close = day_candles.iloc[-1]['close']
            trend_higher_low = day_close > day_open # Bullish day candle

        regimes.append({
            "Date": d.isoformat(),
            "Role": role,
            "Ribbon": ribbon_state,
            "BullWindow": trend_higher_low
        })
        
    return pd.DataFrame(regimes)

def produce_verdict(df_15, df_4h):
    # Logic to check if TP is separable
    
    tp_row = df_15[df_15['Role']=='TP'].iloc[0]
    fp_rows = df_15[df_15['Role']=='FP']
    
    rules = []
    
    # Check Count
    min_tp_count = tp_row['Count']
    max_fp_count = fp_rows['Count'].max()
    if min_tp_count > max_fp_count:
        rules.append(f"IF Count >= {min_tp_count} (TP={min_tp_count} vs FP_max={max_fp_count})")
        
    # Check Vol
    if tp_row['VolPeak'] > fp_rows['VolPeak'].max():
        rules.append(f"IF VolPeak > {fp_rows['VolPeak'].max():.2f}")
        
    # Check FT2
    if tp_row['FT2_Avg'] > fp_rows['FT2_Avg'].max():
        rules.append(f"IF FT_Avg > {fp_rows['FT2_Avg'].max():.2f}")
        
    md = "# AAVE GLOBAL FAKEOUT VERDICT\n\n"
    if rules:
        md += "## DISTINGUISHABLE\n"
        md += "AAVE separates TP from FPs with:\n"
        for r in rules: md += f"- {r}\n"
    else:
        md += "## INDISTINGUISHABLE (GLOBAL MODE)\n"
        md += "No clean 15M signature separates 12-02 from fakeouts.\n"
        
    md += "\n### 15M Data\n"
    md += df_15.to_markdown(index=False)
    md += "\n\n### 4H Regime\n"
    md += df_4h.to_markdown(index=False)
    
    with open(OUT_DIR / "AAVE_GLOBAL_FAKEOUT_VERDICT.md", "w") as f:
        f.write(md)
        
    print(md)

if __name__ == "__main__":
    df15 = get_15m_signatures()
    df4h = get_4h_regime()
    
    df15.to_csv(OUT_DIR / "AAVE_FP_TP_15M_SIGNATURES.csv", index=False)
    df4h.to_csv(OUT_DIR / "AAVE_4H_REGIME_COMPARISON.csv", index=False)
    
    produce_verdict(df15, df4h)
