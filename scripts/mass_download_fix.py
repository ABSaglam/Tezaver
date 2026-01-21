import sys
import os
import time
import pandas as pd
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.data.binance_client import BinanceClient
from tezaver.core import coin_cell_paths

def mass_download():
    print("🚀 TEZAVER MASS DOWNLOADER (2023-2025)")
    print("   Target: 1w, 1d, 4h, 1h for ALL 622+ Coins")
    
    root = "coin_cells"
    if not os.path.exists(root):
        print("❌ 'coin_cells' directory not found.")
        return

    coins = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    coins.sort()
    
    client = BinanceClient()
    
    # We want data starting from 2023-01-01
    start_ts = int(datetime(2023, 1, 1).timestamp() * 1000)
    
    # Timeframes to fetch
    timeframes = ['1w', '1d', '4h', '1h']
    
    total = len(coins)
    
    for i, symbol in enumerate(coins, 1):
        print(f"\n[{i}/{total}] Checking {symbol}...")
        
        # Skip Futures-like tickers for now as Spot client won't find them
        if symbol.startswith("1000"):
            print(f"   ⚠️ Skipping potential Futures ticker: {symbol}")
            continue
            
        data_dir = os.path.join(root, symbol, "data")
        os.makedirs(data_dir, exist_ok=True)
        
        for tf in timeframes:
            file_name = f"history_{tf}.parquet"
            path = os.path.join(data_dir, file_name)
            
            # Check if exists and is up-to-date (at least contains 2024 data)
            needs_download = True
            if os.path.exists(path):
                try:
                    # Quick check of last date
                    df_check = pd.read_parquet(path, columns=['timestamp'])
                    last_ts = df_check['timestamp'].max()
                    last_date = pd.to_datetime(last_ts, unit='ms')
                    
                    if last_date.year >= 2025:
                        needs_download = False # Already good
                        # print(f"   ✅ {tf} is up-to-date ({last_date.date()})")
                    else:
                        print(f"   🔄 {tf} needs update (Last: {last_date.date()})")
                        needs_download = True # Force update
                except:
                    needs_download = True
            
            if needs_download:
                print(f"   ⬇️ Downloading {tf}...", end=" ", flush=True)
                try:
                    # Reuse download logic similar to existing script
                    ccxt_symbol = symbol.replace('USDT', '/USDT')
                    
                    # Fetch Loop
                    all_records = []
                    current_since = start_ts
                    end_ms = int(datetime.now().timestamp() * 1000)
                    
                    while current_since < end_ms:
                        records = client.fetch_ohlcv(ccxt_symbol, tf, since=current_since, limit=1000)
                        if not records: break
                        
                        for rec in records:
                            all_records.append({
                                'timestamp': rec.timestamp,
                                'open': rec.open, 'high': rec.high, 'low': rec.low, 'close': rec.close, 'volume': rec.volume,
                                # Add extras if available, but basic OHLCV is strictly needed
                            })
                        
                        current_since = records[-1].timestamp + 1
                        time.sleep(0.05) # Rate limit
                        
                        # Safety break if we are past now (should be handled by while, but good to be safe)
                        if current_since > end_ms: break
                        
                    if all_records:
                        df = pd.DataFrame(all_records)
                        df = df.drop_duplicates(subset=['timestamp'], keep='last')
                        df.sort_values('timestamp', inplace=True)
                        
                        # Add datetime col for compatibility
                        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                        
                        df.to_parquet(path, index=False)
                        print(f"✓ Saved {len(df)} bars")
                    else:
                        print("⚠️ No data found (Symbol might be delisted/futures)")
                        
                except Exception as e:
                    print(f"❌ Error: {str(e)[:50]}")
                    time.sleep(0.5)

if __name__ == "__main__":
    mass_download()
