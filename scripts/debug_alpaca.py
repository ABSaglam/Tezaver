
import sys
import os
import pandas as pd
# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ALPACAUSDT'
    print(f"🐞 DEBUG RALLIES: {symbol}")
    
    # 1. Check Rallies
    rallies = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=False)
    print(f"Rally Count (ALL TIERS): {len(rallies)}")
    
    if len(rallies) > 0:
        sample_date = next(iter(rallies.keys()))
        print(f"Sample Rally Date: {sample_date} (Type: {type(sample_date)})")
    
    # 2. Check Data
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    if os.path.exists(h4_path):
        df = pd.read_parquet(h4_path)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        print(f"Data Range: {df['datetime'].min()} -> {df['datetime'].max()}")
        print(f"Rows: {len(df)}")
        
        # Check overlap
        df['date'] = df['datetime'].dt.date
        matches = df['date'].isin(rallies.keys()).sum()
        print(f"Data Rows matching Rally Dates: {matches}")
    else:
        print("❌ 4H Data File Missing")

if __name__ == "__main__":
    main()
