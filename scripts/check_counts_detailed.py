
import sys
from pathlib import Path
sys.path.append(str(Path.cwd() / "src"))

import pandas as pd
from tezaver.core.rally_store import RallyStore

def check_counts_detailed():
    store = RallyStore()
    print("Fetching ALL rallies (limit 200,000)...")
    rallies = store.list_rallies(limit=200000)
    
    if not rallies:
        print("DB Empty.")
        return
        
    df = pd.DataFrame(rallies)
    
    print(f"\nTotal: {len(df)}")
    
    print("\n--- Breakdown by Timeframe ---")
    print(df['timeframe'].value_counts())
    
    print("\n--- Breakdown by Tier ---")
    print(df['tier'].value_counts())
    
    print("\n--- Breakdown by Timeframe AND Tier ---")
    # Group by TF and Tier
    print(df.groupby(['timeframe', 'tier']).size())

if __name__ == "__main__":
    check_counts_detailed()
