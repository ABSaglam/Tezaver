
import sys
import os
from pathlib import Path

# Add src to pythonpath
sys.path.insert(0, os.path.abspath("src"))

from tezaver.foundry.rally_assembler import RallyAssembler
from tezaver.core.rally_store import RallyStore
from tezaver.core.annotations import SniperStatus

def diagnose():
    print("=== DIAGNOSTIC START ===")
    
    # 1. Check DB File
    store = RallyStore()
    print(f"DB Path: {store.db_path}")
    if not store.db_path.exists():
        print("CRITICAL: DB FILE DOES NOT EXIST!")
        return
        
    # 2. Raw Count
    conn = store._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM rallies")
    count = cur.fetchone()[0]
    print(f"Total Rows in DB: {count}")
    
    # 3. Check BTCUSDT 15m (Fast15)
    print("\n--- Checking BTCUSDT 15m ---")
    asm = RallyAssembler()
    rallies = asm.get_assembled_rallies("BTCUSDT", "15m")
    print(f"Assembler returned: {len(rallies)} rallies")
    
    if rallies:
        r = rallies[0]
        print(f"Sample Rally: {r.event_id}")
        print(f"  Status: {r.status}")
        print(f"  Tier: {r.tier}")
        print(f"  Gain: {r.gain_pct}")
        print(f"  Display: {r.display_label}")
    else:
        print("No rallies returned for BTCUSDT 15m.")
        
    # 4. Check BTCUSDT 1h (TimeLabs)
    print("\n--- Checking BTCUSDT 1h ---")
    rallies_1h = asm.get_assembled_rallies("BTCUSDT", "1h")
    print(f"Assembler returned: {len(rallies_1h)} rallies")
    
    # 5. Check Filtering Logic (Molder)
    print("\n--- Molder Logic Check (BTCUSDT 1h) ---")
    moldable = asm.get_moldable_rallies("BTCUSDT", "1h")
    print(f"Moldable (Approved) Rallies: {len(moldable)}")
    
    # 6. Check Tier Distribution
    tiers = {}
    for r in moldable:
        t = r.tier or "NONE"
        tiers[t] = tiers.get(t, 0) + 1
    print(f"Tier Distribution: {tiers}")

if __name__ == "__main__":
    diagnose()
