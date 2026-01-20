
from db_helper import get_rallies
import datetime

def main():
    # Load rally data
    rallies = get_rallies('AGIXUSDT', tiers=['DIAMOND', 'GOLD', 'SILVER'])
    
    # The signals were generated on T (row date), meaning the rally started T+1 (next_date).
    # Signal 1: Row 2023-05-11 -> Rally Start 2023-05-12
    # Signal 2: Row 2024-04-12 -> Rally Start 2024-04-13
    
    target_dates = [
        datetime.date(2023, 5, 12),
        datetime.date(2024, 4, 13)
    ]
    
    print(f"Checking {len(target_dates)} signals for AGIXUSDT...")
    
    for d in target_dates:
        if d in rallies:
            # db_helper returns (tier, gain, ...) usually?
            # Let's verify what it returns.
            # Usually it is a tuple. 
            # Based on previous scripts: tier = rally_results[next_date][0]
            data = rallies[d]
            print(f"📅 {d}: {data}")
        else:
            print(f"📅 {d}: NOT FOUND in DB keys!")
            # Print nearby keys just in case
            print(f"   Nearby keys: {[k for k in rallies.keys() if abs((k-d).days) < 5]}")

if __name__ == "__main__":
    main()
