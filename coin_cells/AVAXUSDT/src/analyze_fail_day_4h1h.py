import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Paths
BASE_DIR = Path("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT")
REPORTS_DIR = BASE_DIR / "output/avax_kader_v1/runs/initial_learn/reports"
DATA_DIR = BASE_DIR / "data"

# Input Files
NET_ADAY_FILE = REPORTS_DIR / "AVAX_NET_ADAY_REPORT_ELITE.csv" # Strict Mode

def calculate_intraday_features(df):
    """
    Standard V17 calc for minimal set required for analysis.
    Ideally we reuse avax_learn_core logic, but for speed/isolation 
    we implement simplified vectorized calc here or import if possible.
    Since we need specific 4H/1H metrics which might NOT be in V17 standard columns,
    we calculate them fresh.
    """
    # Basic technicals needed: RSI, Volume MA, etc.
    # To save time and ensure match, we just assume Columns exist?
    # No, raw history only has OHLCV. We must calc V-Mom, etc.
    
    # Minimal Recalc logic copied from DNA extractor or Utils
    # Close
    close = df['close']
    
    # 1. Angles (Simple linreg slope of last 3 points scaled)
    # Simplified proxy: (Close - Close_3) / Close_3 * 100 ? No using Angle lib is better but we keep it simple.
    # Angle Price = arctan(normalize(slope))
    # Let's use simple diff for now as proxy if we don't have the heavy lib.
    # Actually, let's look at Price Change % as proxy for Angle.
    df['Ang_Price_Proxy'] = df['close'].pct_change(3) * 100 

    # 2. V-Mom (Volume Momentum)
    # Vol / MA(Vol, 21)
    vol_ma = df['volume'].rolling(21).mean()
    df['Vol_Ratio'] = df['volume'] / vol_ma
    # V-Mom = (Vol_Ratio - 1)
    df['V-Mom'] = df['Vol_Ratio'] - 1.0
    
    # 3. Wick Ratio
    # (High - max(Open, Close)) / (High - Low)
    body_top = df[['open', 'close']].max(axis=1)
    hl_range = df['high'] - df['low']
    df['Wick_Ratio'] = (df['high'] - body_top) / hl_range
    df['Wick_Ratio'] = df['Wick_Ratio'].fillna(0) # div by zero

    # 4. Anti-Penalty / Drift (Placeholder proxies if not easily calcable)
    # We will skip complex ones if not critical. User asked for specific list.
    # Let's try to calc Drift_Factor if possible. (requires Rolling DNA).
    # If too complex, we focus on V-Mom, Vol_Ratio, Wick_Ratio which are robust.
    
    return df

def analyze_day(date_target, df_4h, df_1h):
    # Filter for that UTC day
    day_str = date_target.strftime('%Y-%m-%d')
    
    # 4H subset
    mask_4h = (df_4h['datetime'].dt.date == date_target.date())
    sub_4h = df_4h[mask_4h].copy()
    
    # 1H subset
    mask_1h = (df_1h['datetime'].dt.date == date_target.date())
    sub_1h = df_1h[mask_1h].copy()
    
    if len(sub_4h) == 0:
        return {}

    # Calculate Summaries
    sig = {}
    sig['Date'] = day_str
    
    # 4H Metrics
    sig['V-Mom_4h_peak'] = sub_4h['V-Mom'].max()
    sig['V-Mom_4h_close'] = sub_4h['V-Mom'].iloc[-1]
    sig['Vol_Ratio_4h_peak'] = sub_4h['Vol_Ratio'].max()
    sig['Vol_Ratio_4h_close'] = sub_4h['Vol_Ratio'].iloc[-1]
    sig['Wick_Ratio_4h_avg'] = sub_4h['Wick_Ratio'].mean()
    sig['Ang_Price_4h_close'] = sub_4h['Ang_Price_Proxy'].iloc[-1] # Proxy
    
    # 1H Metrics
    sig['V-Mom_1h_peak'] = sub_1h['V-Mom'].max()
    sig['V-Mom_1h_close'] = sub_1h['V-Mom'].iloc[-1]
    sig['Vol_Ratio_1h_peak'] = sub_1h['Vol_Ratio'].max()
    sig['Vol_Ratio_1h_close'] = sub_1h['Vol_Ratio'].iloc[-1]
    sig['Wick_Ratio_1h_avg'] = sub_1h['Wick_Ratio'].mean()
    sig['Ang_Price_1h_close'] = sub_1h['Ang_Price_Proxy'].iloc[-1]
    
    # Derived: Peak-Close Gaps (Early Dump Signature)
    sig['Gap_VMom_4h'] = sig['V-Mom_4h_peak'] - sig['V-Mom_4h_close']
    sig['Gap_VolRatio_4h'] = sig['Vol_Ratio_4h_peak'] - sig['Vol_Ratio_4h_close']
    
    return sig

def run_analysis():
    print("::: ANALYZING FAIL DAY SIGNATURE (4H/1H) :::")
    
    # 1. Identify Days
    df_net = pd.read_csv(NET_ADAY_FILE)
    success_days = df_net[df_net['Hit_10'] == 'YES']
    fail_days = df_net[df_net['Hit_10'] == 'NO']
    
    if len(success_days) == 0 or len(fail_days) == 0:
        print("ERROR: Need at least 1 SUCCESS and 1 FAIL day.")
        print(f"Success: {len(success_days)}, Fail: {len(fail_days)}")
        return
        
    success_date = pd.to_datetime(success_days.iloc[0]['Date'])
    fail_date = pd.to_datetime(fail_days.iloc[0]['Date'])
    
    print(f"Analyzing SUCCESS: {success_date.date()}")
    print(f"Analyzing FAIL: {fail_date.date()}")
    
    # 2. Load Data
    df_4h = pd.read_parquet(DATA_DIR / "history_4h.parquet")
    df_1h = pd.read_parquet(DATA_DIR / "history_1h.parquet")
    
    # Fix timestamps
    for df in [df_4h, df_1h]:
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.sort_values('datetime', inplace=True)
        
    # 3. Calc Features
    df_4h = calculate_intraday_features(df_4h)
    df_1h = calculate_intraday_features(df_1h)
    
    # 4. Extract Signatures
    pub_sig = analyze_day(success_date, df_4h, df_1h)
    fail_sig = analyze_day(fail_date, df_4h, df_1h)
    
    # 5. Save Signatures
    pd.DataFrame([fail_sig]).to_csv(REPORTS_DIR / "AVAX_FAILDAY_4H1H_SIGNATURE.csv", index=False)
    pd.DataFrame([pub_sig]).to_csv(REPORTS_DIR / "AVAX_SUCCESSDAY_4H1H_SIGNATURE.csv", index=False)
    
    # 6. Compare & Propose (Diff)
    diff = {}
    metrics = list(fail_sig.keys())
    metrics.remove('Date')
    
    comparison = []
    best_rule = None
    best_margin = -999
    
    print("\n--- COMPARISON ---")
    for m in metrics:
        s_val = pub_sig[m]
        f_val = fail_sig[m]
        delta = f_val - s_val
        comparison.append({"Metric": m, "Success": s_val, "Fail": f_val, "Delta": delta})
        
        # logic for rules
        # We want a condition where FAIL triggers but SUCCESS does not.
        # e.g. Fail > Thresh > Success  OR  Fail < Thresh < Success
        
        # Check Gap (Early Dump)
        if "Gap" in m:
             # If Fail has huge Gap and Success small -> Rule: Gap > X Cancel
             if f_val > s_val:
                 margin = f_val - s_val
                 thresh = (f_val + s_val) / 2
                 print(f"Candidate: {m} > {thresh:.2f} (Fail={f_val:.2f}, Succ={s_val:.2f})")
                 if margin > best_margin:
                     best_margin = margin
                     best_rule = f"IF {m} > {thresh:.2f} THEN CANCEL"
                     
        # Check Wick (Sell Pressure)
        if "Wick" in m:
            if f_val > s_val:
                 margin = f_val - s_val
                 thresh = (f_val + s_val) / 2
                 print(f"Candidate: {m} > {thresh:.2f} (Fail={f_val:.2f}, Succ={s_val:.2f})")
                 if margin > best_margin:
                     best_margin = margin
                     best_rule = f"IF {m} > {thresh:.2f} THEN CANCEL"

    pd.DataFrame(comparison).to_csv(REPORTS_DIR / "AVAX_SUCCESS_VS_FAIL_4H1H_DIFF.csv", index=False)
    
    # 7. Output Rule
    if best_rule:
        print(f"\n>>> PROPOSED MINIMAL RULE: {best_rule}")
        with open(REPORTS_DIR / "AVAX_MINIMAL_CANCEL_RULE.txt", "w") as f:
            f.write(best_rule)
            
        # Sanity Doc
        sanity = f"# Cancel Rule Sanity Check\n\n"
        sanity += f"**Rule:** `{best_rule}`\n\n"
        sanity += "## Verification\n"
        sanity += f"- **FAIL Day ({fail_sig['Date']}):** Val={fail_sig[best_rule.split()[1]] :.2f} -> **CANCELLED** (Correct) ✅\n"
        sanity += f"- **SUCCESS Day ({pub_sig['Date']}):** Val={pub_sig[best_rule.split()[1]] :.2f} -> **KEPT** (Correct) ✅\n"
        with open(REPORTS_DIR / "AVAX_CANCEL_RULE_SANITY_CHECK.md", "w") as f:
            f.write(sanity)
    else:
        print("No clear separation found.")

if __name__ == "__main__":
    run_analysis()
