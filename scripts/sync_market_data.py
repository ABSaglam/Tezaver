import sys
import os
import time
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.data.binance_client import BinanceClient
from tezaver.core import coin_cell_paths
from tezaver.features.indicator_engine import build_features_for_symbol_timeframe
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def sync_data(timeframes=['1d', '4h']):
    client = BinanceClient()
    total_symbols = len(DEFAULT_COINS)
    
    print("=" * 80)
    print(f"🚀 MARKET DATA SYNC START ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"Symbols: {total_symbols}")
    print("=" * 80)
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        print(f"[{i}/{total_symbols}] {symbol} güncelleniyor...")
        
        for tf in timeframes:
            try:
                # 1. Load existing data
                path = coin_cell_paths.get_history_file(symbol, tf)
                existing_df = pd.DataFrame()
                if path.exists():
                    existing_df = pd.read_parquet(path)
                    if 'timestamp' not in existing_df.columns and 'ts' in existing_df.columns:
                        existing_df['timestamp'] = existing_df['ts'] * 1000
                
                # 2. Fetch latest bars (limit 500 is very safe and enough for few days)
                ccxt_symbol = symbol.replace('USDT', '/USDT')
                records = client.fetch_ohlcv(ccxt_symbol, tf, limit=500)
                
                if records:
                    new_data = []
                    for rec in records:
                        new_data.append({
                            'timestamp': rec.timestamp,
                            'open': rec.open,
                            'high': rec.high,
                            'low': rec.low,
                            'close': rec.close,
                            'volume': rec.volume
                        })
                    new_df = pd.DataFrame(new_data)
                    
                    # 3. Merge and deduplicate
                    if not existing_df.empty:
                        combined_df = pd.concat([existing_df, new_df])
                        combined_df = combined_df.drop_duplicates(subset=['timestamp'], keep='last')
                    else:
                        combined_df = new_df
                    
                    combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
                    
                    # Ensure datetime exists
                    combined_df['datetime'] = pd.to_datetime(combined_df['timestamp'], unit='ms', utc=True)
                    
                    # 4. Save
                    path.parent.mkdir(parents=True, exist_ok=True)
                    combined_df.to_parquet(path, index=False)
                    # print(f"    ✓ {tf} güncellendi ({len(combined_df)} mum)")
                
                time.sleep(0.05) # Tiny delay to respect rate limit
                
            except Exception as e:
                print(f"    ❌ {tf} Hatası: {str(e)[:50]}")
        
        # 5. Optional: Build features after symbol sync (Fast but adds time)
        try:
            for tf in timeframes:
                build_features_for_symbol_timeframe(symbol, tf)
            # print(f"    ✓ Features hesaplandı")
        except Exception as e:
            print(f"    ⚠️ Features Hatası: {str(e)[:50]}")

    print("\n" + "=" * 80)
    print(f"✅ SYNC COMPLETED AT {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    sync_data()
