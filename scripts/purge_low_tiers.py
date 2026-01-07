
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("library/rallies.db")

def purge_low_tiers():
    if not DB_PATH.exists():
        print("DB not found")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check counts before
    cur.execute("SELECT tier, count(*) FROM rallies GROUP BY tier")
    print("Before:", cur.fetchall())
    
    # Delete IRON and BRONZE
    # Note: Tier names are stored as strings. 
    # Logic in rally_grade_cards.py maps: 
    # 0-5% -> "IRON"
    # 5-10% -> "BRONZE"
    # 10-20% -> "SILVER"
    # 20-30% -> "GOLD"
    # >30% -> "DIAMOND"
    
    # Also delete based on gain if tier is missing/wrong? 
    # Gain is inside JSON, harder to query. Trust 'tier' column.
    
    cur.execute("DELETE FROM rallies WHERE tier IN ('IRON', 'BRONZE')")
    print(f"Deleted {cur.rowcount} rows.")
    
    conn.commit()
    
    cur.execute("SELECT tier, count(*) FROM rallies GROUP BY tier")
    print("After:", cur.fetchall())
    
    conn.close()

if __name__ == "__main__":
    purge_low_tiers()
