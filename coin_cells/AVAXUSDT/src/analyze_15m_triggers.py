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

def detect_triggers(df):
    """
    Simulate Ignition Trigger Logic:
    - Candle Color: Close > Open
    - Volume: > 1.5 * MA(21) (Lowered slightly to catch all potential)
    - RSI: > 50
    """
    # 1. Basic Features
    df['is_green'] = df['close'] > df['open']
    
    # Vol MA
    vol_ma = df['volume'].rolling(21).mean()
    df['vol_ratio'] = df['volume'] / vol_ma
    
    # RSI (Simple approx or skip if complex lib needed, user said 'M15_RSI' is input)
    # We will compute simple RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Ignition Logic
    # Trigger if Green, Vol > 1.5, RSI > 50
    condition = (df['is_green']) & (df['vol_ratio'] > 1.5) & (df['rsi'] > 50)
    
    df['is_trigger'] = condition
    
    # Ignition Type (Simplified)
    # If Vol Ratio > 3.0 -> EXPLOSIVE
    # Else -> STANDARD
    df['impulse_type'] = np.where(df['vol_ratio'] > 3.0, "EXPLOSIVE", "STANDARD")
    
    return df

def analyze_follow_through(df):
    # Calculate returns 2 bars later
    # We want: (Close_t+2 - Close_t) / Close_t
    df['close_t2'] = df['close'].shift(-2)
    df['follow_through_pct'] = (df['close_t2'] - df['close']) / df['close'] * 100
    return df

def analyze_day_triggers(df, date_str):
    target = pd.to_datetime(date_str).date()
    # Filter day
    mask = df['datetime'].dt.date == target
    day_df = df[mask].copy()
    
    if len(day_df) == 0:
        return []
        
    triggers = day_df[day_df['is_trigger']].copy()
    
    results = []
    for _, row in triggers.iterrows():
        # Store metadata
        results.append({
            "Date": date_str,
            "Timestamp": row['datetime'].time(),
            "Ignition_Type": row['impulse_type'],
            "M15_Vol": round(row['vol_ratio'], 2),
            "M15_RSI": round(row['rsi'], 1),
            "Follow_Through_2bar": round(row['follow_through_pct'], 2)
        })
        
    return results

def run_analysis():
    print("::: 15M MICRO STRUCTURE ANALYSIS :::")
    
    # 1. Load Data
    fpath = DATA_DIR / "history_15m.parquet"
    if not fpath.exists():
        print("Data not found")
        return
        
    df = pd.read_parquet(fpath)
    if 'timestamp' in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    elif 'date' in df.columns:
        df['datetime'] = pd.to_datetime(df['date'], utc=True)
        
    df = df.sort_values('datetime')
    
    # 2. Detect Logic
    df = detect_triggers(df)
    df = analyze_follow_through(df)
    
    # 3. Analyze Days
    fail_trigs = analyze_day_triggers(df, FAIL_DATE)
    succ_trigs = analyze_day_triggers(df, SUCCESS_DATE)
    
    all_trigs = fail_trigs + succ_trigs
    df_out = pd.DataFrame(all_trigs)
    
    # Save CSV
    out_csv = REPORTS_DIR / "AVAX_15M_TRIGGERS_FAIL_VS_SUCCESS.csv"
    df_out.to_csv(out_csv, index=False)
    print(f"Trigger Report: {out_csv}")
    print(df_out)
    
    # 4. Generate Quality Report & Verdict
    # Natural Filter Logic:
    # "FAIL gününde, Trigger var ama Hiçbiri 2 bar sonrası yapı korumuyor mu?"
    # Structure protected = Follow Through > -0.2% (Allow minimal noise, but no dump)
    # Ideally > 0.
    
    # Check Fail Day
    fail_has_triggers = len(fail_trigs) > 0
    fail_valid_triggers = [t for t in fail_trigs if t['Follow_Through_2bar'] > -0.1]
    
    natural_filter = False
    verdict_text = ""
    
    if not fail_has_triggers:
        natural_filter = True
        verdict_text = "NATURAL_FILTER = TRUE. No triggers detected on Fail Day."
    elif len(fail_valid_triggers) == 0:
        natural_filter = True
        verdict_text = "NATURAL_FILTER = TRUE. All triggers failed to hold structure (2-bar dump)."
    else:
        natural_filter = False
        verdict_text = f"NATURAL_FILTER = FALSE. {len(fail_valid_triggers)} triggers held structure."
        
    # Write Verdict
    with open(REPORTS_DIR / "AVAX_15M_DO_NOT_TRADE_VERDICT.txt", "w") as f:
        f.write(verdict_text)
        if not natural_filter:
            f.write("\n\nValid Triggers on Fail Day:\n")
            for t in fail_valid_triggers:
                f.write(str(t) + "\n")

    # Comparative MD
    md = "# 🔬 15M TRIGGER QUALITY DIFFERENCE\n\n"
    
    md += f"## FAIL DAY ({FAIL_DATE})\n"
    md += f"- **Trigger Count:** {len(fail_trigs)}\n"
    if fail_trigs:
        avg_ft = np.mean([t['Follow_Through_2bar'] for t in fail_trigs])
        md += f"- **Avg Follow Through:** {avg_ft:.2f}%\n"
        md += f"- **Structure Holding (> -0.1%):** {len(fail_valid_triggers)}/{len(fail_trigs)}\n"
    else:
        md += "- **No Triggers.**\n"
        
    md += f"\n## SUCCESS DAY ({SUCCESS_DATE})\n"
    md += f"- **Trigger Count:** {len(succ_trigs)}\n"
    if succ_trigs:
        valid_succ = [t for t in succ_trigs if t['Follow_Through_2bar'] > -0.1]
        avg_ft = np.mean([t['Follow_Through_2bar'] for t in succ_trigs])
        md += f"- **Avg Follow Through:** {avg_ft:.2f}%\n"
        md += f"- **Structure Holding:** {len(valid_succ)}/{len(succ_trigs)}\n"
        
    with open(REPORTS_DIR / "AVAX_15M_TRIGGER_QUALITY_DIFF.md", "w") as f:
        f.write(md)

if __name__ == "__main__":
    run_analysis()
