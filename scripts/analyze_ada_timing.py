import json
import pandas as pd
from tezaver.core.rally_store import RallyStore

def analyze_ada_timing():
    symbol = "ADAUSDT"
    with open(f"data/final_v3_{symbol}.json", "r") as f:
        final_v3 = json.load(f)
    with open(f"data/profiles_{symbol}.json", "r") as f:
        all_profiles = json.load(f)
        
    allowed_families = set(final_v3.get('allowed_families', []))
    
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    rally_days = {pd.Timestamp(r['event_time']).normalize(): r.get('tier') for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']}

    t0_count = 0
    t1_count = 0
    both_count = 0
    
    for d_str, p in all_profiles.items():
        key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}"
        if key in allowed_families:
            date = pd.Timestamp(d_str)
            has_t0 = date in rally_days
            has_t1 = (date + pd.Timedelta(days=1)) in rally_days
            
            if has_t0: t0_count += 1
            if has_t1 and not has_t0: t1_count += 1
            if has_t0 and has_t1: both_count += 1

    total = t0_count + t1_count
    print(f"\n⏰ ADA SIGNAL LATENCY ANALYSIS (n={total}):")
    print(f"Total Signals: {total}")
    print(f"Triggered in T=0 (0-24h): {t0_count} ({t0_count/total*100:.1f}%)")
    print(f"Triggered in T=1 (24-48h): {t1_count} ({t1_count/total*100:.1f}%)")
    print(f"Triggered on both days: {both_count}")

if __name__ == "__main__":
    analyze_ada_timing()
