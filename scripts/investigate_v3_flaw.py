import json
import pandas as pd
from collections import Counter

def red_team_investigation():
    symbol = "ADAUSDT"
    print(f"🕵️ RED TEAM INVESTIGATION: {symbol}")
    
    with open(f"data/final_v3_{symbol}.json", "r") as f:
        final_v3 = json.load(f)
    
    with open(f"data/profiles_{symbol}.json", "r") as f:
        all_profiles = json.load(f)
        
    allowed_families = set(final_v3.get('allowed_families', []))
    signals = final_v3.get('signals')
    
    print(f"\n1️⃣ MEMORIZATION CHECK (Ezbercilik Testi)")
    print(f"Total Signals: {signals}")
    print(f"Total Unique Allowed Families: {len(allowed_families)}")
    
    # Check frequency of each family in the SIGNAL set
    signal_families = []
    for d_str, p in all_profiles.items():
        key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}"
        if key in allowed_families:
            signal_families.append(key)
    
    counts = Counter(signal_families)
    single_hit_wonders = sum(1 for k, v in counts.items() if v == 1)
    
    print(f"Families with exactly 1 hit (One-Hit Wonders): {single_hit_wonders}")
    print(f"Ratio of Memorization: {single_hit_wonders / len(allowed_families) * 100:.1f}%")
    
    if single_hit_wonders / len(allowed_families) > 0.8:
        print("⚠️ CRITICAL ALARM: The system is mostly 'memorizing' exact days rather than finding recurring patterns.")
    else:
        print("✅ PASS: The system is using shared patterns (families) to find multiple signals.")

    print(f"\n2️⃣ GRANULARITY CHECK (Çözünürlük Testi)")
    total_days = len(all_profiles)
    unique_profiles_total = len(set(
        f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}" 
        for p in all_profiles.values()
    ))
    
    print(f"Total Days Scanned: {total_days}")
    print(f"Total Unique Profiles in History: {unique_profiles_total}")
    print(f"Uniqueness Ratio: {unique_profiles_total/total_days*100:.1f}%")
    
    if unique_profiles_total / total_days > 0.9:
        print("⚠️ HIGH RISK: The profiles are so detailed (Atomic) that almost every day implies a unique profile.")
        print("   -> This makes 'Zero FP' trivial because you just blacklist the days that aren't rallies.")
        print("   -> It's like using the 'Date' as a feature.")
    
    print(f"\n3️⃣ LEAKAGE CHECK (Sızma Testi)")
    # Logic verification
    print("Verifying if the profile on DAY X is strictly calculated using data UP TO DAY X (Close).")
    print("If we detect a Signal on DAY X (based on Day X profile), does the Rally happen on DAY X or DAY X+1?")
    
    # We rely on the analysis logic here.
    # If the system claims 'T0' hit, it means DAY X profile (Closed candle) matched, and DAY X was a rally.
    # WAIT. If Day X closed candle is used to profile Day X...
    # And Day X IS the rally day...
    # Then we are using the Rally's own +20% close to predict "There will be a rally".
    # THIS IS THE LEAK.
    
    print("Logical Audit:")
    print(" -> Profile(Day_i) uses Close(Day_i)")
    print(" -> Signal(Day_i) means Profile(Day_i) is valid.")
    print(" -> Hit(Day_i) means Rally occurred on Day_i.")
    print(" -> If Profile(Day_i) contains 'Ritim=Ignited' (High Volume + Price Move)...")
    print(" -> And Hit(Day_i) is true...")
    print(" -> Then we effectively said: 'If price moved up today, then price moved up today.'")
    print("🚨 POTENTIAL TAUTOLOGY DETECTED.")
    
if __name__ == "__main__":
    red_team_investigation()
