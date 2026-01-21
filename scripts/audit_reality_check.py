import json
import pandas as pd
from tezaver.core.rally_store import RallyStore

def audit_t_minus_1_reality():
    symbol = "ADAUSDT"
    print(f"🕵️ REALITY CHECK (T-1) FOR {symbol}")
    print("Hypothesis: The current system cheats by seeing the rally candle before predicting it.")
    print("Test: We will run the EXACT SAME allowed families, but we will check if they appear on T-1 (The day BEFORE the rally).")
    
    with open(f"data/final_v3_{symbol}.json", "r") as f:
        final_v3 = json.load(f)
    with open(f"data/profiles_{symbol}.json", "r") as f:
        all_profiles = json.load(f)
        
    allowed_families = set(final_v3.get('allowed_families', []))
    
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    rally_days = {pd.Timestamp(r['event_time']).normalize(): r.get('tier', 'SILVER') for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']}

    # T-1 MATCHING LOGIC
    # Ideally: If Profile(Day_i) is valid -> Rally on Day_i+1
    
    hits = 0
    signals = 0
    
    for d_str, p in all_profiles.items():
        date = pd.Timestamp(d_str)
        key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}"
        
        if key in allowed_families:
            signals += 1
            # PREDICTION: Look ahead to TOMORROW (Day+1)
            target_day = date + pd.Timedelta(days=1)
            
            if target_day in rally_days:
                hits += 1
            else:
                pass 
                # Fail
                
    print(f"\n📊 REALITY RESULTS:")
    print(f"Signals Generated (Based on Families): {signals}")
    print(f"True Predictive Hits (Rally on T+1): {hits}")
    print(f"Predictive Accuracy: {hits/signals*100:.2f}%")
    
    if hits == 0:
        print("\n🚨 CONFIRMED: The logic failed completely when forced to predict T+1.")
        print("   The system was recognizing the 'Crash Scene' (Rally already happened) rather than predicting it.")
    elif hits < 10:
        print("\n⚠️ WEAK PREDICTION: The system has very little predictive power.")
    else:
        print("\n✅ VALID: The system actually predicts tomorrow's rally.")

if __name__ == "__main__":
    audit_t_minus_1_reality()
