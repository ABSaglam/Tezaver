
import sys
from pathlib import Path
sys.path.append(str(Path.cwd() / "src"))

from tezaver.core.rally_store import RallyStore
import json

def repair_timeframes():
    store = RallyStore()
    conn = store._get_conn()
    cursor = conn.cursor()
    
    # 1. Find UNKNOWN timeframes
    cursor.execute("SELECT id, symbol, tier, raw_data FROM rallies WHERE timeframe = 'UNKNOWN'")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} UNKNOWN rallies.")
    
    fixed_count = 0
    
    for row in rows:
        rid, sym, tier, raw_json = row
        
        # Heuristic 1: Extract from ID
        # Format: SYMBOL_TF_TIER_TIMESTAMP or similar
        # e.g. BTCUSDT_1d_DIAMOND_...
        
        tf = "UNKNOWN"
        parts = rid.split('_')
        
        # Check known TFs
        for t in ["5m", "15m", "1h", "4h", "1d", "1w"]:
            if f"_{t}_" in rid:
                tf = t
                break
        
        if tf != "UNKNOWN":
            # Update DB
            cursor.execute("UPDATE rallies SET timeframe = ? WHERE id = ?", (tf, rid))
            
            # Update Raw Data JSON if possible
            if raw_json:
                try:
                    data = json.loads(raw_json)
                    if data.get('timeframe') != tf:
                        data['timeframe'] = tf
                        new_json = json.dumps(data)
                        cursor.execute("UPDATE rallies SET raw_data = ? WHERE id = ?", (new_json, rid))
                except:
                    pass
            
            fixed_count += 1
            if fixed_count % 1000 == 0:
                print(f"Fixed {fixed_count}...")
                conn.commit()
                
    conn.commit()
    conn.close()
    
    print(f"Repair Complete. Fixed {fixed_count} rallies.")

if __name__ == "__main__":
    repair_timeframes()
