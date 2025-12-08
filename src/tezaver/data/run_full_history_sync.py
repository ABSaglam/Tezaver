"""
Script to synchronize full history (last 2 years) for all tracked coins.
Handles pagination and rate limiting to respect Binance limits.
Usage: python src/tezaver/data/run_full_history_sync.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Setup path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tezaver.data.binance_client import BinanceClient
from tezaver.core.config import DEFAULT_COINS, DEFAULT_HISTORY_TIMEFRAMES
from tezaver.data.history_service import save_history, symbol_to_ccxt_pair
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def timeframe_to_ms(tf: str) -> int:
    """Simple timeframe to milliseconds converter."""
    if tf == "1m": return 60 * 1000
    if tf == "5m": return 5 * 60 * 1000
    if tf == "15m": return 15 * 60 * 1000
    if tf == "1h": return 60 * 60 * 1000
    if tf == "4h": return 4 * 60 * 60 * 1000
    if tf == "1d": return 24 * 60 * 60 * 1000
    if tf == "1w": return 7 * 24 * 60 * 60 * 1000
    raise ValueError(f"Unknown timeframe: {tf}")

def fetch_full_history(client: BinanceClient, symbol: str, tf: str, start_ts: int):
    """
    Fetches history from start_ts until now using pagination.
    Returns DataFrame.
    """
    all_records = []
    cursor = start_ts
    tf_ms = timeframe_to_ms(tf)
    pair = symbol_to_ccxt_pair(symbol)
    
    logger.info(f"  Fetching {symbol} {tf} from {datetime.fromtimestamp(cursor/1000)}")
    
    while True:
        try:
            # Fetch batch
            records = client.fetch_ohlcv(symbol, tf, since=cursor, limit=1000)
            
            if not records:
                break
                
            all_records.extend(records)
            
            last_record = records[-1]
            last_ts = last_record.timestamp
            
            # Update cursor to next bar
            cursor = int(last_ts + tf_ms)
            
            # Stop if we reached current time (basic check)
            if cursor > time.time() * 1000:
                break
                
            # Rate limit sleep
            time.sleep(0.5) 
            
            # Print progress dot
            print(".", end="", flush=True)
            
        except Exception as e:
            logger.error(f"Error fetching chunk for {symbol} {tf}: {e}")
            time.sleep(5) # Backoff on error
            # Try once more or continue? Let's just break to avoid infinite loops in bad state
            break
            
    print() # Newline
    
    # Convert to DataFrame
    data = [
        {
            "timestamp": r.timestamp,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume
        }
        for r in all_records
    ]
    
    df = pd.DataFrame(data)
    if not df.empty:
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        # Drop duplicates
        df = df.drop_duplicates(subset=["timestamp"], keep="last")
        df = df.sort_values("timestamp").reset_index(drop=True)
        
    return df

import argparse

def main():
    parser = argparse.ArgumentParser(description="Synchronize full history.")
    parser.add_argument("--days", type=int, default=730, help="Number of days to look back.")
    args = parser.parse_args()

    # Calculate start time
    start_dt = datetime.now() - timedelta(days=args.days)
    start_ts = int(start_dt.timestamp() * 1000)
    
    logger.info(f"Starting Full History Sync (Last {args.days} Days) from {start_dt}")
    
    client = BinanceClient()
    
    for symbol in DEFAULT_COINS:
        logger.info(f"Processing {symbol}...")
        
        for tf in DEFAULT_HISTORY_TIMEFRAMES:
            try:
                df = fetch_full_history(client, symbol, tf, start_ts)
                
                if not df.empty:
                    save_history(symbol, tf, df)
                    logger.info(f"  Saved {len(df)} bars for {symbol} {tf}")
                else:
                    logger.warning(f"  No data found for {symbol} {tf}")
                    
            except Exception as e:
                logger.error(f"Failed to process {symbol} {tf}: {e}")
                
        # Extra sleep between coins
        time.sleep(1.0)
        
    logger.info("Main User: Full History Sync Complete!")

if __name__ == "__main__":
    main()
