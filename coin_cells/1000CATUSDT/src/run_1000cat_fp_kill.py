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

BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/1000CATUSDT")
RUN_001 = BASE_DIR / "output/kader_v3_fixed/runs/run_001"
RUN_002 = BASE_DIR / "output/kader_v3_fixed/runs/run_002"
DATA_DIR = BASE_DIR / "data"

def calculate_rsi_internal(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_15m_metrics(df_15m, target_date):
    if df_15m is None or len(df_15m) == 0:
        return 0, 0
        
    sub15 = df_15m[df_15m['datetime'].dt.date == target_date].copy()
    if len(sub15) == 0:
        return 0, 0
        
    if 'volume' not in sub15.columns: return 0,0
    
    # Indicators
    sub15['EMA21'] = sub15['close'].ewm(span=21, adjust=False).mean()
    if 'RSI' not in sub15.columns:
        sub15['RSI'] = calculate_rsi_internal(sub15['close'])
        
    mean_vol = sub15['volume'].mean()
    sub15['VolRatio'] = sub15['volume'] / mean_vol if mean_vol > 0 else 0
    
    # Triggers
    trigs = sub15[
        (sub15['close'] > sub15['EMA21']) & 
        (sub15['VolRatio'] > 2.0) & 
        (sub15['RSI'] > 50)
    ]
    count = len(trigs)
    burst = 0
    
    if count > 0:
        times = trigs['datetime'].sort_values()
        for t in times:
            end_t = t + pd.Timedelta(hours=1)
            c = len(times[(times >= t) & (times < end_t)])
            if c > burst: burst = c
            
    return count, burst

def check_corridor(row, corr):
    for col, bands in corr.items():
        val = row.get(col)
        if val is not None:
            if val < bands['min'] or val > bands['max']:
                return False, col
    return True, None

def run_002():
    print("::: RUN 002: FP KILL (1000CATUSDT) :::")
    
    # Setup Output
    RUN_002.mkdir(parents=True, exist_ok=True)
    (RUN_002 / "rules").mkdir(exist_ok=True)
    (RUN_002 / "reports").mkdir(exist_ok=True)
    
    # Copy Rules
    for f in ["1000catusdt_fail_rules.json", "1000catusdt_intraday_cancel_rules.json", "1000catusdt_success_corridor.json"]:
        shutil.copy(RUN_001 / "rules" / f, RUN_002 / "rules" / f)
        
    # Update Trigger Map
    with open(RUN_001 / "rules/1000catusdt_trigger_map.json") as f:
        trig_map = json.load(f)
        
    trig_map['trigger_count_min'] = 9
    trig_map['trigger_burstiness_max_per_hour'] = 3
    trig_map['rule_note'] = "FP-KILL: sustainable accumulation, anti-pump"
    
    with open(RUN_002 / "rules/1000catusdt_trigger_map.json", "w") as f:
        json.dump(trig_map, f, indent=4)
        
    # Load Data
    bundle = utils_io.get_data_bundle("1000CATUSDT")
    df = avax_learn_core.calculate_technical_features(bundle['1d'], None, None, None)
    df = core_indicators_v3.calculate_extended_indicators(df)
    df6 = avax_learn_core.generate_labels(df)
    
    df4h = core_indicators_v3.calculate_extended_indicators(bundle['4h'])
    
    # Load 15m
    f15 = DATA_DIR / "1000CATUSDT_15m.csv"
    if not f15.exists():
        f15_pq = DATA_DIR / "history_15m.parquet"
        if f15_pq.exists():
             df15 = pd.read_parquet(f15_pq)
        else:
             print("Warning: 15m data missing, Trigger Gate will fail all.")
             df15 = None
    else:
        df15 = pd.read_csv(f15)
        
    if df15 is not None:
        if 'timestamp' in df15.columns:
             df15['datetime'] = pd.to_datetime(df15['timestamp'], unit='ms', utc=True)
        elif 'open_time' in df15.columns:
             df15['datetime'] = pd.to_datetime(df15['open_time'], unit='ms', utc=True)
    
    # Load Rules
    with open(RUN_002 / "rules/1000catusdt_fail_rules.json") as f: fail = json.load(f)
    with open(RUN_002 / "rules/1000catusdt_success_corridor.json") as f: corr = json.load(f)
    with open(RUN_002 / "rules/1000catusdt_intraday_cancel_rules.json") as f: cancel = json.load(f)
    
    # Simulation
    df_test = df6.iloc[-100:].copy()
    results = []
    logs = []
    
    for idx, row in df_test.iterrows():
        target_date = row['datetime'].date()
        daily_gate = True
        gate_stop = ""
        
        # 1. FAIL RULES
        for col, limits in fail.items():
            if col=="suppression_veto": continue
            val = row.get(col)
            if val:
                if val < limits.get('min_hard', -999): daily_gate = False; gate_stop = f"{col}_LOW_VETO"
                if val > limits.get('max_hard', 999): daily_gate = False; gate_stop = f"{col}_HIGH_VETO"
                
        if fail.get('suppression_veto', {}).get('active') and row.get('STATE_RIBBON_SUPPRESSION_UP'):
             daily_gate = False; gate_stop = "SUPPRESSION_VETO"
             
        # 2. CORRIDOR
        if daily_gate:
            passed, fail_col = check_corridor(row, corr)
            if not passed:
                daily_gate = False; gate_stop = f"{fail_col}_OUT"
                
        # 3. CANCEL
        is_canceled = False
        cancel_why = ""
        if daily_gate:
            df_4h_day = df4h[df4h['datetime'].dt.date == target_date]
            if len(df_4h_day) > 0:
                body_top = df_4h_day[['open', 'close']].max(axis=1)
                hl = (df_4h_day['high'] - df_4h_day['low']).replace(0, np.nan)
                mean_wick = ((df_4h_day['high'] - body_top) / hl).fillna(0).mean()
                if mean_wick > cancel.get('wick_ratio_4h',{}).get('threshold', 0.28):
                    is_canceled = True; cancel_why = f"WICK_4H ({mean_wick:.2f})"
                    
                if not is_canceled:
                    cnt = len(df_4h_day[df_4h_day['STATE_RIBBON_SUPPRESSION_UP'] == True])
                    if cnt/len(df_4h_day) >= 0.5:
                        is_canceled = True; cancel_why = "RIBBON_TRAP"
                        
        # 4. TRIGGER GATE (FP KILL)
        trig_ok = False
        trig_reason = ""
        t_count = 0
        t_burst = 0
        
        if daily_gate and not is_canceled:
            t_count, t_burst = get_15m_metrics(df15, target_date)
            # LOGIC: Count >= 9 AND Burst <= 3
            if t_count >= 9 and t_burst <= 3:
                trig_ok = True
            else:
                trig_reason = f"TRIG_FAIL (Count={t_count}, Burst={t_burst})"
                
        # FINAL DECISION
        dec = "NO"
        reason = gate_stop
        
        if daily_gate:
            if is_canceled:
                reason = cancel_why
            elif not trig_ok:
                reason = trig_reason
            else:
                dec = "NET_ADAY"
                reason = "V3_MATCH_CONFIRMED"
                
        # Log
        logs.append({
            "Date": row['datetime'].isoformat(),
            "DailyGate": daily_gate,
            "Cancel": is_canceled,
            "FinalDecision": dec,
            "Reason": reason,
            "TriggerCount": t_count,
            "TriggerBurst": t_burst,
            "Hit_10": row['Hit_10']
        })
        
        res_row = {col: row.get(col, 0.0) for col in v17_schema.V17_COLUMNS}
        res_row['Date'] = row['datetime'].isoformat()
        res_row['Symbol'] = "1000CATUSDT"
        res_row['Tier'] = "DIAMOND" if dec == "NET_ADAY" else "SILVER"
        res_row['Audit_Verdict'] = "ONY" if dec == "NET_ADAY" else "RED"
        res_row['Decision'] = dec
        res_row['Reason'] = reason
        results.append(res_row)
        
    df_res = pd.DataFrame(results)
    df_log = pd.DataFrame(logs)
    
    df_res[v17_schema.V17_COLUMNS].to_csv(RUN_002 / "reports/1000CATUSDT_V17_TEST_DAILY.csv", index=False)
    df_res[df_res['Decision']=='NET_ADAY'][v17_schema.V17_COLUMNS].to_csv(RUN_002 / "reports/1000CATUSDT_NET_ADAY_REPORT.csv", index=False)
    df_log.to_csv(RUN_002 / "reports/1000CATUSDT_SIMULATION_STAGE_LOG.csv", index=False)
    
    # Audit MD
    # Compare 001 and 002
    try:
        r1 = pd.read_csv(RUN_001 / "reports/1000CATUSDT_NET_ADAY_REPORT.csv")
        r1_dates = set(pd.to_datetime(r1['Date'], utc=True).apply(lambda x: x.isoformat()).tolist())
    except:
        r1_dates = set()
        
    r2_dates = set(df_res[df_res['Decision']=='NET_ADAY']['Date'].tolist())
    
    dropped = r1_dates - r2_dates
    kept = r1_dates.intersection(r2_dates)
    
    md = "# 1000CATUSDT RUN 002 AUDIT (FP KILL)\n\n"
    md += f"Run 001 Net Adays: {len(r1_dates)}\n"
    md += f"Run 002 Net Adays: {len(r2_dates)}\n\n"
    
    md += "## Dropped Days (Newly Eliminated)\n"
    for d in dropped:
        l = df_log[df_log['Date']==d].iloc[0]
        md += f"- **{d[:10]}:** Reason=`{l['Reason']}` (Hit_10={l['Hit_10']})\n"
        
    md += "\n## Kept Days\n"
    for d in kept:
        l = df_log[df_log['Date']==d].iloc[0]
        md += f"- **{d[:10]}:** Reason=`{l['Reason']}` (Hit_10={l['Hit_10']})\n"
        
    # Stats
    r2_hits = df_log[(df_log['FinalDecision']=='NET_ADAY') & (df_log['Hit_10']=='YES')]
    r2_fp = df_log[(df_log['FinalDecision']=='NET_ADAY') & (df_log['Hit_10']=='NO')]
    
    md += f"\n## Performance Stat\n"
    md += f"- **True Positives:** {len(r2_hits)}\n"
    md += f"- **False Positives:** {len(r2_fp)}\n"
    md += f"- **Hit Rate:** {len(r2_hits)/(len(r2_hits)+len(r2_fp))*100:.1f}% (if count > 0)\n"
    
    with open(RUN_002 / "reports/1000CATUSDT_FP_KILL_AUDIT.md", "w") as f:
        f.write(md)
        
    print("Run 002 Complete.")

if __name__ == "__main__":
    run_002()
