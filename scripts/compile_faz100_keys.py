import glob
import json
import os

INPUT_DIR = "data/faz100_keys_temp"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys.json"

all_keys = {}
stats = {'total_processed': 0, 'kept_keys': 0, 'diamond_keys': 0}

json_files = glob.glob(f"{INPUT_DIR}/*.json")
print(f"Aggregating {len(json_files)} key files...")

for jf in json_files:
    try:
        # Filename: .../SYMBOL_keys.json
        symbol = os.path.basename(jf).replace("_keys.json", "")
        
        with open(jf, 'r') as f:
            data = json.load(f)
            
        # Data format: { "DNA_STRING": {"DIAMOND": 1, "WIN_RATE": 100.0, ...} }
        
        best_dna = None
        best_score = -1
        
        # Filter Logic: Find the absolute best DNA for this coin
        # Criteria: 
        # 1. Must be >= 99% WR (User request: Unquestionable 100%)
        # 2. OR Must have Diamond win (Even 1 Diamond is worth taking risk)
        
        # Actually user said: "sadece 3 sinyal verecek ama o 3 sinyalde %100 mü olacak"
        # So we prioritize PRECISION (WR).
        
        valid_keys = {}
        
        for dna, metrics in data.items():
            wr = metrics.get('WIN_RATE', 0)
            diamonds = metrics.get('DIAMOND', 0)
            total = metrics.get('TOTAL', 0)
            
            # STRICTER PHASE-100 LOGIC
            # Old Logic: diamonds > 0 (Too loose, allowed 1 win 1000 losses)
            # New Logic (Sniper):
            # 1. Pure Perfection: WR >= 95% AND Total >= 2 (At least 2 proofs)
            # 2. High Value consistency: Diamonds >= 3 AND WR >= 80% (Proven Gem Finder)
            
            is_sniper = False
            
            if wr >= 95.0 and total >= 2:
                is_sniper = True
            elif diamonds >= 3 and wr >= 80.0:
                is_sniper = True
                
            if is_sniper:
                valid_keys[dna] = metrics
                stats['kept_keys'] += 1
                if diamonds > 0: stats['diamond_keys'] += 1
        
        if valid_keys:
            all_keys[symbol] = valid_keys
            stats['total_processed'] += 1
            
    except Exception as e:
        print(f"Error reading {jf}: {e}")

# Save Master File
with open(OUTPUT_FILE, 'w') as f:
    json.dump(all_keys, f, indent=2)

print(f"✅ Phase-100 Compilation Code Completed.")
print(f"Total Coins with Phase-100 DNA: {stats['total_processed']}")
print(f"Total DNA Keys Saved: {stats['kept_keys']}")
print(f"Keys with Diamond Potential: {stats['diamond_keys']}")
print(f"Saved to: {OUTPUT_FILE}")
