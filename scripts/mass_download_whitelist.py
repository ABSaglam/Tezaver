import sys
import os
import time
import json
import shutil
import pandas as pd
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.data.binance_client import BinanceClient

def whitelisted_mass_download():
    whitelist_path = "data/spot_whitelist_437.json"
    if not os.path.exists(whitelist_path):
        print("❌ Whitelist file not found. Run fetch_whitelist.py first.")
        return

    with open(whitelist_path, "r") as f:
        target_coins = json.load(f)
        
    print(f"🚀 TEZAVER WHITELISTED DOWNLOADER")
    print(f"   Targets: {len(target_coins)} Verified Spot Coins")
    print(f"   Scope: 2023-2025 | 1w, 1d, 4h, 1h")
    
    root = "coin_cells"
    if not os.path.exists(root):
        os.makedirs(root)

    # 1. CLEANUP PHASE
    # Identify folders in coin_cells that are NOT in the whitelist
    existing = set([d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))])
    whitelist_set = set(target_coins)
    
    to_remove = existing - whitelist_set
    
    if to_remove:
        print("\n🗑️ CLEANUP PHASE: Removing Non-Spot/Delisted Folders...")
        for coin in to_remove:
            path = os.path.join(root, coin)
            print(f"   - Removing: {coin}")
            try:
                shutil.rmtree(path)
            except Exception as e:
                print(f"     ❌ Failed to remove {coin}: {e}")
    else:
        print("\n✨ Coin Cells directory is clean.")

    # 2. DOWNLOAD PHASE
    client = BinanceClient()
    start_ts = int(datetime(2023, 1, 1).timestamp() * 1000)
    timeframes = ['1w', '1d', '4h', '1h']
    
    total = len(target_coins)
    
    for i, symbol in enumerate(target_coins, 1):
        print(f"\n[{i}/{total}] Processing {symbol}...")
        
        data_dir = os.path.join(root, symbol, "data")
        os.makedirs(data_dir, exist_ok=True)
        
        for tf in timeframes:
            file_name = f"history_{tf}.parquet"
            path = os.path.join(data_dir, file_name)
            
            # Check Valid & Up-to-date
            needs_download = True
            if os.path.exists(path):
                try:
                    df = pd.read_parquet(path, columns=['timestamp'])
                    if not df.empty:
                        last_ts = df['timestamp'].max()
                        last_date = pd.to_datetime(last_ts, unit='ms')
                        # If data goes into 2025, we assume it's reasonably fresh or just update it anyway?
                        # User wants missing gaps fixed.
                        if last_date.year >= 2025:
                            # Also check start date?
                            first_ts = df['timestamp'].min()
                            first_date = pd.to_datetime(first_ts, unit='ms')
                            if first_date.year <= 2023:
                                needs_download = False 
                                # print(f"   ✅ {tf} OK ({first_date.date()} -> {last_date.date()})")
                            else:
                                print(f"   🔄 {tf} needs backfill (Starts: {first_date.date()})")
                        else:
                            print(f"   🔄 {tf} needs update (Ends: {last_date.date()})")
                    else:
                        print(f"   🔄 {tf} Empty file")
                except:
                    print(f"   🔄 {tf} Corrupt file")
                    needs_download = True
            
            if needs_download:
                print(f"   ⬇️ Downloading {tf}...", end=" ", flush=True)
                try:
                    ccxt_symbol = symbol.replace('USDT', '/USDT')
                    all_records = []
                    current_since = start_ts
                    end_ms = int(datetime.now().timestamp() * 1000)
                    
                    while current_since < end_ms:
                        records = client.fetch_ohlcv(ccxt_symbol, tf, since=current_since, limit=1000)
                        if not records: break
                        
                        for rec in records:
                            all_records.append({
                                'timestamp': rec.timestamp,
                                'open': rec.open, 'high': rec.high, 'low': rec.low, 'close': rec.close, 'volume': rec.volume
                            })
                        
                        current_since = records[-1].timestamp + 1
                        time.sleep(0.05)
                        if current_since > end_ms: break
                        
                    if all_records:
                        df = pd.DataFrame(all_records)
                        df = df.drop_duplicates(subset=['timestamp'], keep='last')
                        df.sort_values('timestamp', inplace=True)
                        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                        df.to_parquet(path, index=False)
                        print(f"✓ Saved {len(df)} bars")
                    else:
                        print("⚠️ No data returned")
                        
                except Exception as e:
                    print(f"❌ {str(e)[:50]}")
                    time.sleep(1)

if __name__ == "__main__":
    whitelisted_mass_download()
