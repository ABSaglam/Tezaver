import sqlite3
import json
import pandas as pd
import numpy as np

DB_PATH = "/Users/alisaglam/TezaverMac/library/rallies.db"

def analyze():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT tier, raw_data FROM rallies")
    rows = cursor.fetchall()
    conn.close()
    
    data = []
    for tier, raw_json in rows:
        if not raw_json: continue
        try:
            raw = json.loads(raw_json)
            duration = raw.get('bars_to_peak')
            if duration is not None:
                data.append({"tier": tier, "duration": duration})
        except:
            continue
            
    df = pd.DataFrame(data)
    if df.empty:
        print("No duration data found.")
        return
        
    print("\n" + "="*50)
    print("📊 RALLY DURATION ANALYSIS (Average Bars to Peak)")
    print("="*50)
    
    overall_avg = df['duration'].mean()
    print(f"Overall Average: {overall_avg:.1f} bars")
    
    print("\n[Breakdown by Tier]")
    tier_stats = df.groupby('tier')['duration'].agg(['count', 'mean', 'median', 'max']).sort_values('mean', ascending=False)
    
    # Custom sort for tiers
    tier_order = {'DIAMOND': 0, 'GOLD': 1, 'SILVER': 2, 'BRONZE': 3, 'IRON': 4}
    tier_stats = tier_stats.reset_index()
    tier_stats['order'] = tier_stats['tier'].map(tier_order).fillna(99)
    tier_stats = tier_stats.sort_values('order').drop(columns=['order'])
    
    print(tier_stats.to_string(index=False))
    print("="*50)

if __name__ == "__main__":
    analyze()
