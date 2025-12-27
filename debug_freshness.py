
import pandas as pd
from pathlib import Path

def check_file_freshness():
    path = Path("library/fast15_rallies/ADAUSDT/fast15_rallies.parquet")
    if not path.exists():
        print(f"File not found: {path}")
        return
        
    df = pd.read_parquet(path)
    if 'event_time' in df.columns:
        last_date = df['event_time'].max()
        print(f"LAST EVENT DATE IN FILE: {last_date}")
        print(f"TOTAL EVENTS: {len(df)}")
    else:
        print("Column 'event_time' not found.")

if __name__ == "__main__":
    check_file_freshness()
