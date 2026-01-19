import sqlite3
import json
import pandas as pd

def check_test_zone_rallies():
    conn = sqlite3.connect('library/rallies.db')
    cursor = conn.cursor()
    symbols = ['SYNUSDT', 'OMUSDT', 'MDTUSDT', 'RAYUSDT']
    
    test_start = pd.to_datetime('2025-10-01')
    
    print('='*80)
    print(f"{'SYMBOL':<10} | {'DATE':<12} | {'TIER':<10} | {'GAIN':<8}")
    print('-'*80)

    total_count = 0
    for s in symbols:
        cursor.execute("SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ('DIAMOND', 'GOLD')", (s,))
        results = cursor.fetchall()
        for raw_data, tier in results:
            data = json.loads(raw_data)
            dt = pd.to_datetime(data['start_time'])
            if dt >= test_start:
                total_count += 1
                print(f"{s:<10} | {dt.date()} | {tier:<10} | %{data['gain']:.1f}")
    
    print('='*80)
    print(f"TOTAL DIAMOND/GOLD RALLIES IN TEST ZONE: {total_count}")
    conn.close()

if __name__ == "__main__":
    check_test_zone_rallies()
