
import pandas as pd
from pathlib import Path

def check_specific_dates():
    path = Path("library/fast15_rallies/ADAUSDT/fast15_rallies.parquet")
    if not path.exists(): return
        
    df = pd.read_parquet(path)
    df['event_time'] = pd.to_datetime(df['event_time'])
    
    targets = [
        "2025-10-10", "2025-10-11",
        "2025-03-02", "2025-03-03",
        "2024-11-09", "2024-11-10", # Nov 9-10
        "2024-11-22"
    ]
    
    print(f"SEARCHING IN RADAR FILE ({len(df)} total events)...")
    
    found_count = 0
    for t_str in targets:
        ts = pd.to_datetime(t_str)
        # Check matching day
        matches = df[df['event_time'].dt.date == ts.date()]
        if not matches.empty:
            print(f"\n📅 FOUND RALLIES ON {t_str}:")
            for _, row in matches.iterrows():
                print(f"   - Time: {row['event_time']} | Gain: {row['future_max_gain_pct']*100:.1f}% | Bucket: {row['rally_bucket']}")
            found_count += len(matches)
        
    if found_count == 0:
        print("❌ NO MATCHES FOUND for target dates.")
    else:
        print(f"\nTotal Matches Found: {found_count}")

if __name__ == "__main__":
    check_specific_dates()
