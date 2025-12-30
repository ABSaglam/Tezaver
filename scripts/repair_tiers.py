
import sys
import os
import json
import sqlite3
from pathlib import Path

# Add src to pythonpath
sys.path.insert(0, os.path.abspath("src"))

from tezaver.core.rally_store import RallyStore
from tezaver.core.tier_utils import compute_tier_from_gain

def repair_tiers():
    print("=== REPAIRING TIERS IN SQLITE ===")
    store = RallyStore()
    conn = store._get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("SELECT id, raw_data, tier FROM rallies")
    rows = cur.fetchall()
    print(f"Found {len(rows)} rallies. Analysing...")
    
    updates = []
    
    for row in rows:
        eid = row['id']
        curr_tier = row['tier']
        raw_json = row['raw_data']
        
        if not raw_json:
            continue
            
        try:
            raw = json.loads(raw_json)
            gain = raw.get('future_max_gain_pct')
            if gain is None:
                continue
                
            new_tier = compute_tier_from_gain(gain)
            
            # If changed/unknown, update
            if curr_tier == 'UNKNOWN' or curr_tier != new_tier:
                updates.append((new_tier, eid))
                
        except Exception as e:
            print(f"Error parsing {eid}: {e}")
            
    print(f"Determined {len(updates)} tier fixes.")
    
    if updates:
        print("Applying updates...")
        cur.executemany("UPDATE rallies SET tier = ? WHERE id = ?", updates)
        conn.commit()
        print("SUCCESS: Tiers repaired.")
    else:
        print("No updates needed.")
        
    conn.close()

if __name__ == "__main__":
    repair_tiers()
