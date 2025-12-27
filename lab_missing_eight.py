
import pandas as pd
from pathlib import Path
from datetime import timedelta

def investigate_missing_eight():
    symbol = "ADAUSDT"
    path = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
    
    if not path.exists(): return
        
    df = pd.read_parquet(path)
    if 'event_time' in df.columns:
        df['event_time'] = pd.to_datetime(df['event_time'])
    
    # These are the 8 "New Discoveries" from Precision Radar (12H) - UTC Times
    # We want to see if they exist in the scanner DB (any tier)
    targets_utc = [
        ("2024-11-09 15:00:00", "9 Nov Afternoon"), # 21.0% in 12h
        ("2024-11-09 21:00:00", "9 Nov Night"),     # ?
        ("2024-11-10 01:00:00", "10 Nov Morning"),  # 32.2% in 12h
        ("2024-12-20 12:00:00", "20 Dec Rally"),    # 25.7% in 12h
        ("2025-02-03 04:30:00", "3 Feb Early"),     # 23.3% in 12h
        ("2025-03-04 13:15:00", "4 Mar Rally"),     # 22.1% in 12h
        ("2023-12-08 04:00:00", "8 Dec 23 Rally"),  # 22.8% in 12h
        # Add others from previous tool output manually if recall matches
    ]
    
    print("🕵️‍♂️ MISSING 8 INVESTIGATION REPORT")
    print("Checking if 'Big 12H Rallies' are hiding in Lower Tiers...")
    print("="*80)
    
    for t_str, label in targets_utc:
        target_ts = pd.to_datetime(t_str)
        
        # Look for events within +/- 3 hours window
        window_start = target_ts - timedelta(hours=3)
        window_end = target_ts + timedelta(hours=3)
        
        matches = df[(df['event_time'] >= window_start) & (df['event_time'] <= window_end)]
        
        if matches.empty:
            print(f"❌ {label} ({t_str} UTC): NOT FOUND in Scanner DB")
        else:
            print(f"✅ {label} ({t_str} UTC): FOUND!")
            for _, row in matches.iterrows():
                # Convert to TR
                ts_tr = row['event_time'] + timedelta(hours=3)
                tier = row['rally_bucket']
                gain = row['future_max_gain_pct'] * 100
                print(f"   -> System recorded it at {ts_tr} (TR) as [{tier}] with Gain: {gain:.1f}%")
                
                if tier == "30p_plus":     print("      (It IS a Diamond!)")
                elif tier == "20p_30p":    print("      (It is GOLD - Downgraded from 12H view)")
                elif tier == "10p_20p":    print("      (It is SILVER - Significantly Downgraded)")
                else:                      print("      (It is BRONZE)")

    print("="*80)

if __name__ == "__main__":
    investigate_missing_eight()
