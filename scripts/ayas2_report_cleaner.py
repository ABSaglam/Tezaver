#!/usr/bin/env python3
import json
import os

BLACKLIST_FILE = "/Users/alisaglam/TezaverMac/data/blacklist_list2.json"
INPUT_REPORT = "/Users/alisaglam/TezaverMac/refined_global_report_list2_only.md"
OUTPUT_REPORT = "/Users/alisaglam/TezaverMac/refined_global_report_list2_CLEANED.md"

def clean_report():
    print(f"Loading blacklist from {BLACKLIST_FILE}...")
    try:
        with open(BLACKLIST_FILE, "r") as f:
            blacklist = set(json.load(f))
    except Exception as e:
        print(f"Error loading blacklist: {e}")
        return

    print(f"Blacklist loaded: {len(blacklist)} coins.")
    
    with open(INPUT_REPORT, "r") as f:
        lines = f.readlines()
        
    cleaned_lines = []
    removed_count = 0
    
    for line in lines:
        # Check if line contains any blacklisted symbol
        # Format: | NO | SYM | ...
        # Simple check: Is the symbol in the line?
        # Be careful about substrings (e.g. USDP in TUSP?)
        # Better: extract symbol column.
        
        if not line.strip().startswith("|") or "---" in line or ("NO" in line and "SYM" in line):
            cleaned_lines.append(line)
            continue
            
        parts = line.split("|")
        if len(parts) > 3:
            sym = parts[2].strip()
            if sym in blacklist:
                removed_count += 1
                continue
        
        cleaned_lines.append(line)
        
    with open(OUTPUT_REPORT, "w") as f:
        f.writelines(cleaned_lines)
        
    print(f"✅ Rapor Temizlendi: {OUTPUT_REPORT}")
    print(f"🗑️ Atılan Satır Sayısı: {removed_count}")

if __name__ == "__main__":
    clean_report()
