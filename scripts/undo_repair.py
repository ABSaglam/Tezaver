
import os
import json
import pandas as pd
from datetime import date
from tezaver.engines.tunnel_engine import TunnelEngine
from tezaver.core.config import COIN_CELLS_DIR

# Correct path for keys
KEYS_DIR = '/Users/alisaglam/TezaverMac/data/golden_keys'

def undo_repair(target_dates):
    # Initialize engine to calculate DNA
    engine = TunnelEngine()
    # Ensure engine points to correct dir if needed, but we use KEYS_DIR directly
    
    # We need to access the DNA generation logic.
    # TunnelEngine.check_permission calls _get_profile_simple.
    # We can use check_permission to get the DNA.
    
    print(f"Starting Undo for dates: {target_dates}")
    
    # Get all key files
    key_files = [f for f in os.listdir(KEYS_DIR) if f.endswith('_key.json')]
    print(f"Scanning {len(key_files)} key files...")
    
    total_removed = 0
    files_modified = 0
    
    for filename in key_files:
        sym = filename.replace('_key.json', '')
        key_path = os.path.join(KEYS_DIR, filename)
        
        try:
            with open(key_path, 'r') as f:
                data = json.load(f)
        except:
            continue
            
        original_len = len(data.get('golden_dna_list', []))
        if original_len == 0: continue
        
        modified = False
        
        # For this coin, calculate the DNA for the target dates
        dnas_to_remove = set()
        
        for day_num in target_dates:
            target_date = date(2026, 1, day_num)
            try:
                # We don't need to mock anything, just get the DNA
                _, _, dna = engine.check_permission(sym, target_date)
                if dna and dna != "neutral":
                    dnas_to_remove.add(dna)
            except:
                pass
                
        # Remove them from the list
        if dnas_to_remove:
            new_list = [d for d in data['golden_dna_list'] if d not in dnas_to_remove]
            
            if len(new_list) < original_len:
                diff = original_len - len(new_list)
                data['golden_dna_list'] = new_list
                data['unique_dna_count'] = len(new_list)
                
                with open(key_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                total_removed += diff
                files_modified += 1
                # print(f"Cleaned {sym}: Removed {diff} entries.")
                
    print(f"Undo Complete.")
    print(f"Files Modified: {files_modified}")
    print(f"Total DNA Entries Removed: {total_removed}")

if __name__ == "__main__":
    # Undo Jan 26 and 27
    undo_repair([26, 27])
