import sys
import os
sys.path.append(os.getcwd())
import pandas as pd
import numpy as np
import json
from datetime import timedelta
from tezaver.core.rally_store import RallyStore

def build_algo_journey_memory():
    symbol = "ALGOUSDT"
    print(f"🧠 Building Journey Memory for {symbol} (2023-2025)")
    print("="*80)
    
    # 1. Load Rallies
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    
    memory = []
    
    for r in all_rallies:
        date = pd.Timestamp(r['event_time']).normalize()
        if date.year not in [2023, 2024, 2025]: continue
        
        # Classification from Store Tier
        tier = r.get('tier')
        if tier not in ['DIAMOND', 'GOLD', 'SILVER']: continue
        
        gain = r.get('raw_data', {}).get('gain', 0)
        
        journey_offsets = [1, 3, 5, 7, 14, 21]
        precursors = []
        for offset in journey_offsets:
            p_day = date - timedelta(days=offset)
            precursors.append(p_day.strftime('%Y-%m-%d'))
            
        memory.append({
            'rally_date': date.strftime('%Y-%m-%d'),
            'type': tier,
            'pnl': round(gain, 2),
            'journey_days': precursors
        })
        
    # Stats
    df_mem = pd.DataFrame(memory)
    print(f"Captured {len(df_mem)} DGS Rallies.")
    print(df_mem['type'].value_counts())
    
    # Save Memory
    out_path = "data/algo_journey_memory.json"
    with open(out_path, 'w') as f:
        json.dump(memory, f, indent=2)
        
    print(f"\n✅ Journey Memory saved to {out_path}")

if __name__ == "__main__":
    build_algo_journey_memory()
