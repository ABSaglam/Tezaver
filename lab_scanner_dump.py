
import pandas as pd
from pathlib import Path
from datetime import timedelta

def run_scanner_dump():
    symbol = "ADAUSDT"
    path = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
    
    if not path.exists():
        print(f"File not found: {path}")
        return
        
    print(f"🔓 RAW SCANNER DUMP: {symbol}")
    print("Listing ALL detected rallies (No Filter / No Approver)")
    print("="*60)
    
    df = pd.read_parquet(path)
    if 'event_time' in df.columns:
        df['event_time'] = pd.to_datetime(df['event_time'])
    
    # Sort descending by gain
    df = df.sort_values('future_max_gain_pct', ascending=False)
    
    # Buckets
    tiers = {
        "DIAMOND 💎": "30p_plus",
        "GOLD 🥇": "20p_30p",
        "SILVER 🥈": "10p_20p",
        "BRONZE 🥉": "5p_10p"
    }
    
    total_found = len(df)
    
    for tier_name, bucket_id in tiers.items():
        subset = df[df['rally_bucket'] == bucket_id]
        count = len(subset)
        if count == 0: continue
        
        print(f"\n{tier_name} ({count} Events)")
        print("-" * 60)
        
        # Show top 20 of each tier (or all if distinct)
        # Sort by Time for the list
        subset_sorted = subset.sort_values('event_time', ascending=False)
        
        for _, row in subset_sorted.head(20).iterrows():
            ts_utc = row['event_time']
            ts_tr = ts_utc + timedelta(hours=3)
            gain = row['future_max_gain_pct'] * 100
            dur = row['bars_to_peak']
            
            print(f"{ts_tr} (TR) | Gain: {gain:>5.1f}% | Dur: {dur:>3} bars")
            
        if count > 20:
            print(f"... and {count - 20} more.")

    print("\n" + "="*60)
    print(f"TOTAL DETECTED: {total_found}")

if __name__ == "__main__":
    run_scanner_dump()
