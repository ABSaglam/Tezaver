
import sqlite3
import pandas as pd
import json

def main():
    db_path = 'library/rallies.db'
    symbol = 'AERGOUSDT'
    
    print(f"🕵️ DEBUGGING DB for {symbol}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Check count
        cursor.execute("SELECT count(*) FROM rallies WHERE symbol = ?", (symbol,))
        count = cursor.fetchone()[0]
        print(f"Total rows for {symbol}: {count}")
        
        if count == 0:
            print("❌ No rows found! Checking likely symbols...")
            cursor.execute("SELECT DISTINCT symbol FROM rallies WHERE symbol LIKE ?", ('%AERGO%',))
            similar = cursor.fetchall()
            print(f"Similar symbols: {similar}")
        else:
            # 2. Check tiers
            cursor.execute("SELECT tier, count(*) FROM rallies WHERE symbol = ? GROUP BY tier", (symbol,))
            tiers = cursor.fetchall()
            print("\nTier Breakdown:")
            for tier, cnt in tiers:
                print(f"  {tier}: {cnt}")
                
            # 3. Check dates
            cursor.execute("SELECT raw_data FROM rallies WHERE symbol = ? LIMIT 1", (symbol,))
            rows = cursor.fetchall()
            print("\nSample Data Keys:")
            for r in rows:
                data = json.loads(r[0])
                print(f"Keys: {list(data.keys())}")
                print(f"Full Data: {data}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    main()
