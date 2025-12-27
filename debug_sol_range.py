
import pandas as pd
from pathlib import Path

def check_sol_range():
    path = Path("/Users/alisaglam/TezaverMac/coin_cells/SOLUSDT/data/features_15m.parquet")
    if not path.exists():
        print("File missing.")
        return
        
    df = pd.read_parquet(path)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        print(f"SOLUSDT Range: {df['timestamp'].min()}  <--->  {df['timestamp'].max()}")
    else:
        print("Timestamp column missing.")

if __name__ == "__main__":
    check_sol_range()
