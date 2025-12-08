
import pandas as pd
import glob
from pathlib import Path

def measure_performance():
    # Load all available fast15 scan results
    files = glob.glob("library/fast15_rallies/*/fast15_rallies.parquet")
    
    if not files:
        print("No scan files found. Please run 'Fast15 Scan' for at least one coin.")
        return

    all_data = []
    for f in files:
        df = pd.read_parquet(f)
        if 'scenario_id' in df.columns:
            all_data.append(df)
    
    if not all_data:
        print("No data with scenarios found.")
        return
        
    df_all = pd.concat(all_data)
    
    print(f"Total Events Analyzed: {len(df_all)}")
    
    # metrics
    # future_max_gain_pct is the max gain in the lookahead window (21 bars)
    
    # We define "Success" as: Did it hit at least 15% gain? (arbitrary for test)
    # Or simply compare average max gain.
    
    stats = df_all.groupby('scenario_label').agg(
        Count=('future_max_gain_pct', 'count'),
        Avg_Max_Gain=('future_max_gain_pct', lambda x: x.mean() * 100),
        Max_Gain=('future_max_gain_pct', lambda x: x.max() * 100),
        Win_Rate_10pct=('future_max_gain_pct', lambda x: (x > 0.10).mean() * 100)
    ).round(2)
    
    # Sort by Avg Gain
    stats = stats.sort_values('Avg_Max_Gain', ascending=False)
    
    # Set display options
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    
    print("\n--- SCENARIO PERFORMANCE REPORT ---")
    print(stats)
    print("\n-----------------------------------")
    print("Interpretation:")
    print("- Avg_Max_Gain: Average % rise after the signal.")
    print("- Win_Rate_10pct: Probability of PRICE rising at least 10%.")

if __name__ == "__main__":
    measure_performance()
