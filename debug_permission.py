
from tezaver.engines.tunnel_engine import TunnelEngine
import json
import os

def debug_perm():
    symbol = "AVNTUSDT"
    date = "2026-01-27"
    engine = TunnelEngine()
    
    print(f"--- DEBUG PERMISSION: {symbol} on {date} ---")
    
    # 1. Check Key File
    key_path = os.path.join(engine.golden_keys_dir, f"{symbol}_key.json")
    print(f"Key Path: {key_path}")
    if os.path.exists(key_path):
        with open(key_path, 'r') as f:
            data = json.load(f)
            print(f"Key Loaded. DNA Count: {len(data.get('golden_dna_list', []))}")
            # print(f"DNAs: {data.get('golden_dna_list')}")
    else:
        print("❌ KEY FILE MISSING!")
        return

    # 2. Run Permission Check
    has_perm, status, dna = engine.check_permission(symbol, date)
    print(f"\nResult: {has_perm} | Status: {status}")
    print(f"Daily DNA: {dna}")
    
    # 3. Check if DNA is in Key
    if os.path.exists(key_path):
        with open(key_path, 'r') as f:
            data = json.load(f)
            if dna in data.get('golden_dna_list', []):
                print("✅ DNA IS IN LIST (Should match)")
            else:
                print("❌ DNA NOT IN LIST (Mismatch)")

if __name__ == "__main__":
    debug_perm()
