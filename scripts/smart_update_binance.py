"""
Smart Binance Incremental Updater
=================================
Efficiency-first data updater.
Uses a 'Manifest' (data/data_manifest.json) to track the state of every coin/timeframe.
Avoids reading heavy parquet files unless an update is strictly necessary.

Logic:
1. Load Manifest.
2. For each Coin/TF:
   - Check Last Known Timestamp (from Manifest).
   - Compare with Now.
   - If Gap > Threshold -> Download only the gap -> Append -> Update Manifest.
   - If Unknown in Manifest -> Read Parquet Index (once) -> Update Manifest.
"""

import sys
import os
import time
import json
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.data.binance_client import BinanceClient
from tezaver.core import coin_cell_paths

# Configuration
MANIFEST_FILE = Path("data/data_manifest.json")
TARGET_TIMEFRAMES = ["15m", "1h", "4h", "1d"]
STALENESS_THRESHOLD_BARS = 1  # Update if we are behind by more than this many bars

def load_manifest():
    if MANIFEST_FILE.exists():
        try:
            return json.load(open(MANIFEST_FILE, 'r'))
        except:
            return {}
    return {}

def save_manifest(data):
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_last_timestamp_from_parquet(path):
    """Efficiently gets the last timestamp from a parquet file without reading the whole file."""
    if not path.exists():
        return None
    try:
        # Optimization: Read only the last row or metadata if possible.
        # fastparquet or pyarrow can do specific column reading, but pandas read_parquet is robust.
        # We'll read specific columns to be faster, but finding the tail is tricky with standard parquet
        # without reading fully. 
        # For now, we accept reading the file ONCE to index it.
        # Future optimization: Use fastparquet to read footer.
        df = pd.read_parquet(path, columns=['timestamp'])
        if df.empty: return None
        return int(df['timestamp'].max())
    except Exception as e:
        print(f"⚠️ Error reading {path.name}: {e}")
        return None

def download_gap(client, symbol, timeframe, start_ms, end_ms):
    """Downloads data between start_ms and end_ms."""
    ccxt_symbol = symbol.replace('USDT', '/USDT')
    all_records = []
    current_since = start_ms
    
    # Safety: Don't hammer API if gap is huge. (Though we want to fill it)
    # We will loop until we cover the range.
    
    while current_since < end_ms:
        try:
            # fetch_ohlcv gets candles starting AT 'since'.
            # limit usually 1000 for binance
            records = client.fetch_ohlcv(ccxt_symbol, timeframe, since=current_since, limit=1000)
            
            if not records:
                break
            
            last_timestamp = 0
            for rec in records:
                if rec.timestamp > end_ms:
                    continue # Should not happen usually with since
                
                # Filter out exact duplicates of start time if necessary, but usually safe
                if rec.timestamp > start_ms: # Strictly greater than last known
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
            
            # Next fetch starts after the last candle
            # If we got fewer than 1000, we probably reached the head.
            if len(records) < 1000:
                break
                
            current_since = last_timestamp + 1
            time.sleep(0.1) # Respect rate limits
            
        except Exception as e:
            print(f"❌ Error downloading {symbol}: {e}")
            break
            
    if not all_records:
        return None
        
    df = pd.DataFrame(all_records)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    return df

def ms_to_str(ms):
    if not ms: return "NEVER"
    return datetime.fromtimestamp(ms/1000.0).strftime('%Y-%m-%d %H:%M')

def timeframe_to_ms(tf):
    map_ms = {
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
        "1w": 7 * 24 * 60 * 60 * 1000
    }
    return map_ms.get(tf, 15*60*1000)

def run_smart_update():
    print("="*60)
    print("🧠 SMART BINANCE UPDATER v1.0")
    print("="*60)
    
    # 1. Init
    client = BinanceClient()
    manifest = load_manifest()
    
    total_updates = 0
    total_checked = 0
    
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    # Iterate All Coins
    for i, symbol in enumerate(DEFAULT_COINS):
        if symbol not in manifest:
            manifest[symbol] = {}
        
        # Progress for console
        if i % 20 == 0:
            print(f"Checking [{i}/{len(DEFAULT_COINS)}] {symbol} ...")
            
        for tf in TARGET_TIMEFRAMES:
            total_checked += 1
            
            # --- PHASE 1: CHECK STATE ---
            last_ms = manifest[symbol].get(tf)
            
            # If unknown in manifest, check disk
            if last_ms is None:
                path = coin_cell_paths.get_history_file(symbol, tf)
                last_ms_disk = get_last_timestamp_from_parquet(path)
                
                if last_ms_disk:
                    last_ms = last_ms_disk
                    manifest[symbol][tf] = last_ms
                    # Save periodically or just updating dict for now
                else:
                    # New file needed
                    last_ms = 0 # Epoch/None
            
            # Calculate Freshness
            if last_ms == 0:
                # Need full history (or at least a year). 
                # For smart update, let's default to current year start if completely missing
                # Or handle as separate case. For this script, we assume filling gaps.
                # Let's start from 2024 if totally empty.
                 start_gap = int(datetime(2024, 1, 1).timestamp() * 1000)
            else:
                 start_gap = last_ms
                 
            # Threshold Check
            duration_ms = timeframe_to_ms(tf)
            bars_behind = (now_ms - start_gap) / duration_ms
            
            if bars_behind < STALENESS_THRESHOLD_BARS:
                # Fresh enough
                if last_ms and last_ms > 0:
                    manifest[symbol][tf] = last_ms # Ensure correct
                continue
                
            # --- PHASE 2: UPDATE ---
            # Download Gap
            print(f"   ⬇️  Updating {symbol} {tf} (Behind {bars_behind:.1f} bars) ...", end="", flush=True)
            
            new_df = download_gap(client, symbol, tf, start_gap, now_ms)
            
            if new_df is not None and not new_df.empty:
                path = coin_cell_paths.get_history_file(symbol, tf)
                path.parent.mkdir(parents=True, exist_ok=True)
                
                if path.exists():
                    try:
                        old_df = pd.read_parquet(path)
                        combined = pd.concat([old_df, new_df])
                        combined = combined.drop_duplicates(subset=['timestamp'], keep='last')
                        combined = combined.sort_values('timestamp')
                        combined.to_parquet(path, index=False)
                    except:
                        # Corrupt file? Overwrite
                        new_df.to_parquet(path, index=False)
                else:
                    new_df.to_parquet(path, index=False)
                
                # Update Manifest
                actual_last = int(new_df['timestamp'].max())
                manifest[symbol][tf] = actual_last
                print(f" ✅ Done (Up to {ms_to_str(actual_last)})")
                total_updates += 1
            else:
                print(" ⚠️ No new data")
                # Update manifest to now to prevent checking again immmediately if it was empty?
                # No, standard binance might just not have data yet.
        
        # Periodic Save
        if i % 10 == 0:
            save_manifest(manifest)
            
    # Final Save
    save_manifest(manifest)
    
    print("="*60)
    print(f"🎉 Update Complete.")
    print(f"Total Checks: {total_checked}")
    print(f"Total Downloads: {total_updates}")
    print(f"Manifest: {MANIFEST_FILE}")
    print("="*60)

if __name__ == "__main__":
    run_smart_update()
