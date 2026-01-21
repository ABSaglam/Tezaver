import json
import pandas as pd
from tezaver.core.rally_store import RallyStore

def audit_ada_full_history():
    symbol = "ADAUSDT"
    print(f"🕵️ AUDITING FULL HISTORY FOR {symbol} (2023-2025)")
    
    # 1. Load Data
    with open(f"data/profiles_{symbol}.json", "r") as f:
        all_profiles = json.load(f)
    with open(f"data/final_v3_{symbol}.json", "r") as f:
        final_v3 = json.load(f)
    
    allowed_families = set(final_v3.get('allowed_families', []))
    
    # 2. Get Ground Truth Rallies
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    rally_days = {pd.Timestamp(r['event_time']).normalize(): r.get('tier', 'SILVER') for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']}

    total_days = len(all_profiles)
    blocked_days = 0
    true_positives = 0
    false_positives = 0
    
    audit_log = []

    print(f"Processing {total_days} days...")
    
    for date_str, p in all_profiles.items():
        date = pd.Timestamp(date_str)
        key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}"
        
        # Is the gate open for this profile?
        if key in allowed_families:
            # Check if rally followed
            found_rally = False
            r_tier = None
            for d_off in [0, 1]:
                check_day = date + pd.Timedelta(days=d_off)
                if check_day in rally_days:
                    found_rally = True
                    r_tier = rally_days[check_day]
                    break
            
            if found_rally:
                true_positives += 1
                audit_log.append({'date': date_str, 'status': 'PASS', 'result': f'HIT ({r_tier})', 'key': key})
            else:
                false_positives += 1
                audit_log.append({'date': date_str, 'status': 'PASS', 'result': 'FALSE POSITIVE', 'key': key})
        else:
            blocked_days += 1
            # For logging, let's see if we blocked a rally day (False Negative) or a quiet day
            found_rally = False
            for d_off in [0, 1]:
                if date + pd.Timedelta(days=d_off) in rally_days:
                    found_rally = True; break
            
            # audit_log.append({'date': date_str, 'status': 'BLOCK', 'result': 'Rally Missed' if found_rally else 'Clean Block', 'key': key})

    print("\n📊 FULL HISTORY AUDIT RESULTS (ADAUSDT):")
    print(f"Total Days Scanned: {total_days}")
    print(f"Gate Opened (Signals): {true_positives + false_positives}")
    print(f"Gate Closed (Blocked): {blocked_days}")
    print(f"------------------------------------")
    print(f"✅ Success (True Positives): {true_positives}")
    print(f"❌ Error (False Positives): {false_positives}")
    print(f"🎯 Precision: {(true_positives / (true_positives + false_positives) * 100 if (true_positives + false_positives) > 0 else 0):.2f}%")

    if false_positives == 0:
        print("\n🏆 MÜHÜR DOĞRULANDI: Tünel ralli olmayan hiçbir günü geçirmedi.")

if __name__ == "__main__":
    audit_ada_full_history()
