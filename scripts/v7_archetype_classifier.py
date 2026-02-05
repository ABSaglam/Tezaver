import json
import numpy as np

INPUT_FILE = "v7_raw_rallies.json"
OUTPUT_FILE = "v7_classified_rallies.json"

def classify_archetype(event):
    gain = event['gain_pct']
    duration = event['duration_bars'] # 15m bars
    
    # Speed: % per hour
    # duration bars * 15m = minutes. duration / 4 = hours.
    hours = max(0.25, duration / 4)
    speed = gain / hours
    
    # LOGIC RULES
    
    # 💥 SUPERNOVA: Extremely fast, massive gain.
    if speed >= 5.0 and gain >= 15.0: # >5% per hour, total >15%
        return "SUPERNOVA"
        
    # 🥷 NINJA: Fast pop but lower total magnitude or shorter duration
    if speed >= 3.0 and gain >= 10.0:
        return "NINJA"
        
    # 🧗 GRIND: Slow and steady. Low speed, long duration.
    if speed < 2.0 and duration >= 20: # Lasts at least 5 hours
        return "GRIND"
        
    # 🏄 SURFER: Moderate speed, decent gain
    if speed >= 2.0 and speed < 5.0:
        return "SURFER"
        
    return "GENERIC"

def run_classification():
    print("🔬 V7: Archetype Lab Started...")
    
    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)
        
    classified = {}
    stats = {"SUPERNOVA": 0, "NINJA": 0, "GRIND": 0, "SURFER": 0, "GENERIC": 0}
    
    for coin, events in data.items():
        coin_classified = []
        for e in events:
            arch = classify_archetype(e)
            e['archetype'] = arch
            stats[arch] += 1
            coin_classified.append(e)
        classified[coin] = coin_classified
        
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(classified, f, indent=2)
        
    print("✅ Classification Complete.")
    print("----- Archetype Distribution -----")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print(f"📦 Saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_classification()
