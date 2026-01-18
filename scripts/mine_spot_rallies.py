"""
DSG Rally Miner (Silver, Gold, Diamond Only)
============================================
Scans 15m Binance Spot data for all rallies with gain >= 10%.
Populates library/rallies.db.
"""

import sys
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths
from tezaver.mining.rally_miner import mine_rallies, classify_tier
from tezaver.core.rally_store import RallyStore

def run_dsg_mining():
    store = RallyStore()
    total_symbols = len(DEFAULT_COINS)
    total_found = 0
    
    print("=" * 60)
    print(f"🚀 GLOBAL DSG RALLY MINING START ({datetime.now().strftime('%H:%M')})")
    print(f"Total Symbols: {total_symbols}")
    print(f"Criteria: Gain >= 10% (Silver+)")
    print("=" * 60)
    
    start_time = time.time()
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        try:
            path_15m = coin_cell_paths.get_history_file(symbol, '15m')
            if not path_15m.exists():
                continue
                
            df = pd.read_parquet(path_15m)
            
            # Mine rallies with min_gain=0.10 (10%)
            rallies = mine_rallies(df, symbol, max_window=96, min_gain=0.10)
            
            for r in rallies:
                # 1. Classify Tier (redundant but safe)
                tier = classify_tier(r['gain'])
                
                # 2. Create Unique ID: SYMBOL_TF_TIER_TS
                ts = int(pd.to_datetime(r['start_time']).timestamp())
                tier_code = tier[0] # D, G, S
                rally_id = f"{symbol}_15m_{tier_code}_{ts}"
                
                # 3. Store in DB
                store.upsert_rally(rally_id, r, layer='raw')
                total_found += 1
                
            if i % 50 == 0:
                print(f"[{i}/{total_symbols}] {symbol} processed. Found: {total_found}")
                
        except Exception as e:
            print(f"❌ Error mining {symbol}: {e}")
            
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"✅ DSG MINING COMPLETED")
    print(f"Total DSG Rallies Found: {total_found}")
    print(f"Time Taken: {elapsed:.1f}s")
    print(f"Database: library/rallies.db")
    print("=" * 60)

if __name__ == "__main__":
    run_dsg_mining()
