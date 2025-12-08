
import json
import os
from pathlib import Path

FILE_PATH = Path("data/coin_state.json")

def migrate_matic_to_pol():
    if not FILE_PATH.exists():
        print("coin_state.json not found.")
        return

    with open(FILE_PATH, 'r') as f:
        data = json.load(f)

    updated = False
    new_data = []
    
    # Check if POL already exists to avoid duplication
    pol_exists = any(item.get("symbol") == "POLUSDT" for item in data)
    
    for item in data:
        if item.get("symbol") == "MATICUSDT":
            if not pol_exists:
                print("Migrating MATICUSDT -> POLUSDT...")
                item["symbol"] = "POLUSDT"
                item["data_state"] = "missing" # Reset state to force fetch
                item["last_update"] = None
                new_data.append(item)
                updated = True
            else:
                print("Removing MATICUSDT (POLUSDT already exists)...")
                updated = True
                # Skip appending this item
        else:
            new_data.append(item)
    
    # If POLUSDT wasn't in original list and we didn't migrate (maybe MATIC was already gone?),
    # ensure it's added if missing from 'data' but present in config.
    # But for now, just saving the modification is enough.
            
    if updated:
        with open(FILE_PATH, 'w') as f:
            json.dump(new_data, f, indent=2)
        print("Migration complete. coin_state.json updated.")
    else:
        print("No MATICUSDT found or no changes needed.")

if __name__ == "__main__":
    migrate_matic_to_pol()
