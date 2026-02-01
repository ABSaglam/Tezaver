import glob
import json
import re

OUTPUT_FILE = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys.json"
REPORT_FILES = glob.glob("PURE_DNA_REPORT_*.md")

faz100_keys = {}
stats = {'total_coins': 0, 'faz100_found': 0, 'diamond_keys': 0}

print(f"Reading {len(REPORT_FILES)} report files...")

for rfile in REPORT_FILES:
    with open(rfile, 'r') as f:
        for line in f:
            if "|" not in line or "---" in line or "Sembol" in line: continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 8: continue
            
            # Extract Data
            # | **COIN** | %100.0 (3 sinyal) | ... | 💎1 |
            
            coin = parts[1].replace("*", "").replace(" ", "")
            
            # Parse Pure DNA Column
            # Format: "%100.0 (3 sinyal)" OR "%0.0" OR "-"
            pure_col = parts[2]
            
            if "%" not in pure_col: continue
            
            try:
                wr_str = pure_col.split("(")[0].replace("%", "").strip()
                wr = float(wr_str)
            except: wr = 0.0
            
            diamond_col = parts[4].replace("💎", "").strip()
            diamonds = int(diamond_col) if diamond_col.isdigit() else 0
            
            # CRITERIA FOR FAZ-100
            # 1. Win Rate %100 AND Sinyal >= 1 
            # OR
            # 2. Has at least 1 Diamond win (Even if WR < 100, Diamond is precious)
            # User said: "sadece 3 sinyal verecek ama o 3 sinyalde %100 mü olacak" -> Implies High Precision preference.
            # Let's stick to strict 100% WR OR High Diamond count.
            
            if wr >= 99.0 or diamonds > 0:
                # We need the DNA pattern itself!
                # Ah, the report currently DOES NOT show the DNA string, only stats.
                # Mistake in previous step: The report summary hides the DNA string.
                # I need to re-extract the exact DNA key from the script logic or 
                # modify the Pure report to include the Key itself.
                # Or better: The Pure Extraction script returned 'top_dna'.
                # I should have saved the JSON output directly in that script.
                
                # RECOVERY PLAN:
                # Since I cannot extract the DNA string from the markdown report (it's not there),
                # I will create a script that re-runs 'get_dna_signature' logic fast OR
                # modify the extractor to dump JSON.
                # Re-running is expensive. 
                # Wait, I can't get the DNA string from the MD file.
                # I must modify `grand_dna_extractor_pure.py` to save a JSON file alongside MD.
                pass

# Corrective Action:
# I realized the markdown report does NOT contain the DNA string (e.g. 'derin_dip|...'). 
# I need to re-run the extraction with a flag to SAVE JSON. 
# Since re-running takes ~2 mins, it is acceptable. 
