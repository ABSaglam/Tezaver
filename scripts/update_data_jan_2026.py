import sys
import os
import time
import json
import pandas as pd
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.data.binance_client import BinanceClient

def update_fresh_data():
    whitelist_path = "data/spot_whitelist_437.json"
    if not os.path.exists(whitelist_path):
        print("❌ Whitelist not found.")
        return

    with open(whitelist_path, "r") as f:
        target_coins = json.load(f)
        
    print(f"🚀 DATA REFRESH: SYNCING JAN 2026 GAP")
    client = BinanceClient()
    timeframes = ['1d', '4h', '1h', '15m']
    root = "coin_cells"
    
    total = len(target_coins)
    
    for i, symbol in enumerate(target_coins, 1):
        print(f"[{i}/{total}] Updating {symbol}...", end=" ", flush=True)
        data_dir = os.path.join(root, symbol, "data")
        
        for tf in timeframes:
            path = os.path.join(data_dir, f"history_{tf}.parquet")
            if not os.path.exists(path): continue
            
            try:
                df = pd.read_parquet(path)
                last_ts = df['timestamp'].max()
                
                # Fetch from last_ts + 1
                ccxt_symbol = symbol.replace('USDT', '/USDT')
                records = client.fetch_ohlcv(ccxt_symbol, tf, since=last_ts + 1, limit=1000)
                
                if records:
                    new_data = []
                    for rec in records:
                        new_data.append({
                            'timestamp': rec.timestamp,
                            'open': rec.open, 'high': rec.high, 'low': rec.low, 'close': rec.close, 'volume': rec.volume
                        })
                    
                    new_df = pd.DataFrame(new_data)
                    new_df['datetime'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)
                    
                    # Merge and Save
                    final_df = pd.concat([df, new_df]).drop_duplicates(subset=['timestamp'], keep='last').sort_values('timestamp')
                    final_df.to_parquet(path, index=False)
                    print(f"{tf}:+{len(new_data)}", end=" ", flush=True)
                else:
                    print(f"{tf}:OK", end=" ", flush=True)
            except Exception as e:
                print(f"{tf}:ERR({str(e)[:10]})", end=" ", flush=True)
        print("✓")

if __name__ == "__main__":
    update_fresh_data()
