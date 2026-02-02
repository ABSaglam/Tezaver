"""
Smart Binance Incremental Updater - TURBO EDITION
=================================================
Parallel processing version of the smart updater.
Uses ThreadPoolExecutor to handle multiple coins concurrently.
"""

import sys
import os
import time
import json
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.data.binance_client import BinanceClient
from tezaver.core import coin_cell_paths

# Configuration
MANIFEST_FILE = Path("data/data_manifest.json")
TARGET_TIMEFRAMES = ["15m", "1h", "4h", "1d"]
STALENESS_THRESHOLD_BARS = 1
MAX_WORKERS = 10 # Binance rate limits strict usually, but for simple klines it's generous. 10 is safe.

# Global Lock for manifests
manifest_lock = threading.Lock()

def load_manifest():
    if MANIFEST_FILE.exists():
        try:
            return json.load(open(MANIFEST_FILE, 'r'))
        except:
            return {}
    return {}

def save_manifest(data):
    # In turbo mode, we might skip frequent saves or lock it
    # We will save at end or periodically in main thread if architecture allows
    # For now simple overwrite with lock
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_last_timestamp_from_parquet(path):
    if not path.exists(): return None
    try:
        # Optim: Read just columns if possible via pandas
        df = pd.read_parquet(path, columns=['timestamp'])
        if df.empty: return None
        return int(df['timestamp'].max())
    except Exception as e:
        return None

def download_gap(client, symbol, timeframe, start_ms, end_ms):
    ccxt_symbol = symbol.replace('USDT', '/USDT')
    all_records = []
    current_since = start_ms
    
    # Safety loop
    while current_since < end_ms:
        try:
            records = client.fetch_ohlcv(ccxt_symbol, timeframe, since=current_since, limit=1000)
            if not records: break
            
            last_timestamp = 0
            for rec in records:
                if rec.timestamp > end_ms: continue
                if rec.timestamp > start_ms:
                     all_records.append({
                        'timestamp': rec.timestamp,
                        'open': rec.open,
                        'high': rec.high,
                        'low': rec.low,
                        'close': rec.close,
                        'volume': rec.volume
                    })
                last_timestamp = rec.timestamp

            if not records: break
            if len(records) < 1000: break
                
            current_since = last_timestamp + 1
            # Rate limit sleep slightly reduced for parallel checks, client handles basic rate limiting
            time.sleep(0.05) 
            
        except Exception as e:
            # print(f"❌ Error downloading {symbol}: {e}")
            break
            
    if not all_records: return None
    df = pd.DataFrame(all_records)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    return df

def timeframe_to_ms(tf):
    map_ms = {"15m": 900000, "1h": 3600000, "4h": 14400000, "1d": 86400000}
    return map_ms.get(tf, 900000)

def process_coin(symbol, client, local_manifest_entry, now_ms):
    """
    Process a single coin. Returns a dict of updates for the manifest.
    local_manifest_entry: Copy of manifest entry for this symbol.
    """
    updates = {}
    total_dl = 0
    msgs = []

    # If new symbol
    if not local_manifest_entry:
        local_manifest_entry = {}

    for tf in TARGET_TIMEFRAMES:
        last_ms = local_manifest_entry.get(tf)
        
        # Check Disk if unknown
        if last_ms is None:
            path = coin_cell_paths.get_history_file(symbol, tf)
            last_ms_disk = get_last_timestamp_from_parquet(path)
            if last_ms_disk:
                last_ms = last_ms_disk
                updates[tf] = last_ms
            else:
                last_ms = 0
        
        # Freshness Check
        start_gap = last_ms if last_ms > 0 else int(datetime(2024, 1, 1).timestamp() * 1000)
        duration_ms = timeframe_to_ms(tf)
        bars_behind = (now_ms - start_gap) / duration_ms
        
        if bars_behind < STALENESS_THRESHOLD_BARS:
            if last_ms and last_ms > 0: updates[tf] = last_ms # Confirm
            continue
            
        # Download
        # msgs.append(f"   ⬇️  {symbol} {tf} ({bars_behind:.1f} behind)")
        new_df = download_gap(client, symbol, tf, start_gap, now_ms)
        
        if new_df is not None and not new_df.empty:
            path = coin_cell_paths.get_history_file(symbol, tf)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write strategy
            if path.exists():
                try:
                    old_df = pd.read_parquet(path)
                    combined = pd.concat([old_df, new_df]).drop_duplicates(subset=['timestamp'], keep='last').sort_values('timestamp')
                    combined.to_parquet(path, index=False)
                except:
                    new_df.to_parquet(path, index=False)
            else:
                new_df.to_parquet(path, index=False)
                
            actual_last = int(new_df['timestamp'].max())
            updates[tf] = actual_last
            total_dl += 1
            msgs.append(f"✅ {symbol} {tf} updated")
        else:
            # msgs.append(f"⚠️ {symbol} {tf} no data")
            pass
            
    return symbol, updates, total_dl, msgs

def run_turbo_update():
    print("="*60)
    print("🚀 TURBO BINANCE UPDATER v2.0 (Parallel)")
    print(f"Workers: {MAX_WORKERS}")
    print("="*60)
    
    client = BinanceClient() # Thread safety depends on ccxt impl. usually okay if new request per call.
    # Ideally one client per thread, but expensive login. CCXT sync client is blocking, so in threaded it blocks thread.
    # Rate limit is global per IP. 
    
    manifest = load_manifest()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    total_downloads = 0
    futures = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for symbol in DEFAULT_COINS:
            # Pass a copy of the manifest entry or empty dict
            entry = manifest.get(symbol, {}).copy()
            futures.append(executor.submit(process_coin, symbol, client, entry, now_ms))
        
        total_coins = len(DEFAULT_COINS)
        completed = 0
        
        print(f"Queued {total_coins} coins...")
        
        for future in as_completed(futures):
            completed += 1
            try:
                symbol, updates, dl_count, msgs = future.result()
                
                # Update Main Manifest
                if symbol not in manifest: manifest[symbol] = {}
                manifest[symbol].update(updates)
                
                total_downloads += dl_count
                
                # Print status if downloaded
                if dl_count > 0:
                     for msg in msgs:
                         print(msg)
                
                # Periodic Progress Bar
                if completed % 20 == 0:
                    print(f"Progress: {completed}/{total_coins} ...")
                    
                # Periodic Save (Thread Safe block)
                if completed % 50 == 0:
                    save_manifest(manifest)
                    
            except Exception as e:
                print(f"❌ Worker Error: {e}")
                
    # Final Save
    save_manifest(manifest)
    print("="*60)
    print(f"🎉 Turbo Update Complete. Total Downloads: {total_downloads}")
    print("="*60)

if __name__ == "__main__":
    run_turbo_update()
