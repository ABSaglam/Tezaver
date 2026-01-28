"""
Binance Spot USDT Veri İndirme Scripti
======================================
Checkpoint destekli, fazlı indirme.
Kullanım: python download_spot_data.py --tf 15m --year 2025
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.data.binance_client import BinanceClient
from tezaver.core import coin_cell_paths

CHECKPOINT_FILE = Path("data/download_checkpoint.json")

def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        return json.load(open(CHECKPOINT_FILE))
    return {}

def save_checkpoint(data):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(CHECKPOINT_FILE, 'w'))

def get_year_range(year: int):
    """Returns (start_ms, end_ms) for a given year."""
    start = datetime(year, 1, 1, 0, 0, 0)
    if year == 2026:
        end = datetime.now()
    else:
        end = datetime(year, 12, 31, 23, 59, 59)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

def download_symbol(client, symbol, timeframe, start_ms, end_ms, existing_df=None):
    """Downloads all bars for a symbol in chunks, starting from start_ms."""
    all_records = []
    
    # Optimizasyon: Eğer mevcut veri varsa, onun bittiği yerden başla
    current_since = start_ms
    if existing_df is not None and not existing_df.empty:
        last_ms = existing_df['timestamp'].max()
        if last_ms >= end_ms:
            print("✓ Already up to date", end=" ")
            return existing_df
        current_since = last_ms + 1
        print(f" (resuming from {pd.to_datetime(current_since, unit='ms', utc=True)})", end=" ", flush=True)

    ccxt_symbol = symbol.replace('USDT', '/USDT')
    
    while current_since < end_ms:
        try:
            records = client.fetch_ohlcv(ccxt_symbol, timeframe, since=current_since, limit=1000)
            
            if not records:
                break
                
            for rec in records:
                if rec.timestamp <= end_ms:
                    all_records.append({
                        'timestamp': rec.timestamp,
                        'open': rec.open,
                        'high': rec.high,
                        'low': rec.low,
                        'close': rec.close,
                        'volume': rec.volume
                    })
            
            if records:
                current_since = records[-1].timestamp + 1
            else:
                break
                
            time.sleep(0.02)  # Faster rate limit for small updates
            
        except Exception as e:
            print(f"Error: {str(e)[:50]}")
            time.sleep(1)
            break
    
    if not all_records:
        return existing_df
    
    new_df = pd.DataFrame(all_records)
    
    if existing_df is not None and not existing_df.empty:
        combined = pd.concat([existing_df, new_df])
        combined = combined.drop_duplicates(subset=['timestamp'], keep='last')
        combined = combined.sort_values('timestamp').reset_index(drop=True)
    else:
        combined = new_df.sort_values('timestamp').reset_index(drop=True)
    
    combined['datetime'] = pd.to_datetime(combined['timestamp'], unit='ms', utc=True)
    
    return combined

def run_download(timeframe: str, year: int):
    """Main download function with checkpoint support."""
    client = BinanceClient()
    checkpoint = load_checkpoint()
    checkpoint_key = f"{timeframe}_{year}"
    
    completed_symbols = set(checkpoint.get(checkpoint_key, []))
    
    start_ms, end_ms = get_year_range(year)
    
    print("=" * 80)
    print(f"🚀 DOWNLOAD: {timeframe} / {year}")
    print(f"   Symbols: {len(DEFAULT_COINS)}")
    print(f"   Already done: {len(completed_symbols)}")
    print(f"   Remaining: {len(DEFAULT_COINS) - len(completed_symbols)}")
    print("=" * 80)
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if symbol in completed_symbols:
            continue
        
        print(f"[{i}/{len(DEFAULT_COINS)}] {symbol}...", end=" ", flush=True)
        
        try:
            path = coin_cell_paths.get_history_file(symbol, timeframe)
            
            existing_df = None
            if path.exists():
                existing_df = pd.read_parquet(path)
            
            result_df = download_symbol(client, symbol, timeframe, start_ms, end_ms, existing_df)
            
            if result_df is not None and not result_df.empty:
                path.parent.mkdir(parents=True, exist_ok=True)
                result_df.to_parquet(path, index=False)
                print(f"✓ {len(result_df)} bars")
            else:
                print("⚠️ No data")
            
            # Update checkpoint
            completed_symbols.add(symbol)
            checkpoint[checkpoint_key] = list(completed_symbols)
            save_checkpoint(checkpoint)
            
        except Exception as e:
            print(f"❌ {str(e)[:40]}")
    
    print("\n" + "=" * 80)
    print(f"✅ {timeframe}/{year} COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Binance Spot USDT data")
    parser.add_argument("--tf", required=True, help="Timeframe: 15m, 1h, 4h, 1d, 1w")
    parser.add_argument("--year", type=int, required=True, help="Year: 2024, 2025, 2026")
    
    args = parser.parse_args()
    
    run_download(args.tf, args.year)
