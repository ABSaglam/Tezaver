
import sys
import os
# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from db_helper import get_rallies

def main():
    symbol = 'ALICEUSDT'
    rallies = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    counts = {'DIAMOND': 0, 'GOLD': 0, 'SILVER': 0}
    for date, data in rallies.items():
        tier = data[0]
        if tier in counts:
            counts[tier] += 1
            
    print(f"Total DGS: {len(rallies)}")
    print(f"DIAMOND: {counts['DIAMOND']}")
    print(f"GOLD: {counts['GOLD']}")
    print(f"SILVER: {counts['SILVER']}")

if __name__ == "__main__":
    main()
