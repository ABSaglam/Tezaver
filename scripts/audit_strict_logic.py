import json
import pandas as pd
from tezaver.core.rally_store import RallyStore

def audit_strict_prediction():
    symbol = "ADAUSDT"
    print(f"⚖️ STRICT PREDICTION AUDIT FOR {symbol}")
    print("Rule: We throw away the 'Same Day' (T=0) hits because they are Hindsight Bias.")
    print("      We ONLY count a hit if Rally happens on T+1 (Tomorrow).")
    print("      If Profile matches but NO Rally on T+1, it is a FALSE POSITIVE.")
    
    with open(f"data/final_v3_{symbol}.json", "r") as f:
        final_v3 = json.load(f)
    with open(f"data/profiles_{symbol}.json", "r") as f:
        all_profiles = json.load(f)
        
    allowed_families = set(final_v3.get('allowed_families', []))
    
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    rally_days = {pd.Timestamp(r['event_time']).normalize(): r.get('tier', 'SILVER') for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']}

    signals = 0
    true_predictions = 0
    false_positives = 0
    
    for d_str, p in all_profiles.items():
        key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}"
        
        if key in allowed_families:
            signals += 1
            prediction_date = pd.Timestamp(d_str)
            target_date = prediction_date + pd.Timedelta(days=1)
            
            if target_date in rally_days:
                true_predictions += 1
            else:
                false_positives += 1
                
    print(f"\n📊 STRICT PREDICTION RESULTS:")
    print(f"Total Signals (Gate Open): {signals}")
    print(f"✅ True Predictions (Rally Tomorrow): {true_predictions}")
    print(f"❌ False Predictions (No Rally Tomorrow): {false_positives}")
    print(f"REAL PRECISION: {true_predictions/signals*100:.2f}%")
    
    if false_positives > 0:
        print("\n💀 BUSTED: The 'Zero FP' claim was an illusion caused by including T=0 hindsight.")
        print(f"   There are {false_positives} days where the system said 'YES' but the market said 'NO'.")
    else:
        print("\n🏆 MIRACLE: Even with strict T+1 rules, the system has 0 False Positives.")

if __name__ == "__main__":
    audit_strict_prediction()
