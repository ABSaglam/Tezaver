"""
Binance Spot - Tüm Yıllar İndirme Scripti
==========================================
Yıl ayrımı olmadan tüm geçmişi indirir.
Kullanım: python download_all_years.py --tf 1h
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
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

def download_all_history(client, symbol, timeframe):
    """Downloads all available history for a symbol."""
    all_records = []
    ccxt_symbol = symbol.replace('USDT', '/USDT')
    
    # Start from 2024-01-01 (user preference: no data before 2024)
    current_since = int(datetime(2024, 1, 1).timestamp() * 1000)
    end_ms = int(datetime.now().timestamp() * 1000)
    
    while current_since < end_ms:
        try:
            records = client.fetch_ohlcv(ccxt_symbol, timeframe, since=current_since, limit=1000)
            
            if not records:
                break
                
            for rec in records:
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
                
            time.sleep(0.05)
            
        except Exception as e:
            print(f" Error: {str(e)[:40]}")
            time.sleep(1)
            break
    
    if not all_records:
        return None
    
    df = pd.DataFrame(all_records)
    df = df.drop_duplicates(subset=['timestamp'], keep='last')
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    
    return df

def run_download(timeframe: str):
    """Download all history for a timeframe."""
    client = BinanceClient()
    checkpoint = load_checkpoint()
    checkpoint_key = f"{timeframe}_all"
    
    completed_symbols = set(checkpoint.get(checkpoint_key, []))
    
    print("=" * 80)
    print(f"🚀 DOWNLOAD: {timeframe} (All Years)")
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
            
            result_df = download_all_history(client, symbol, timeframe)
            
            if result_df is not None and not result_df.empty:
                path.parent.mkdir(parents=True, exist_ok=True)
                result_df.to_parquet(path, index=False)
                print(f"✓ {len(result_df)} bars")
            else:
                print("⚠️ No data")
            
            completed_symbols.add(symbol)
            checkpoint[checkpoint_key] = list(completed_symbols)
            save_checkpoint(checkpoint)
            
        except Exception as e:
            print(f"❌ {str(e)[:40]}")
    
    print("\n" + "=" * 80)
    print(f"✅ {timeframe} (All Years) COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download all Binance Spot history")
    parser.add_argument("--tf", required=True, help="Timeframe: 1h, 4h, 1d, 1w")
    
    args = parser.parse_args()
    run_download(args.tf)
