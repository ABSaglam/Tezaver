"""
Efficiently synchronizes historical data by filling gaps rather than overwriting.
Targets a specific day-range (default 800 days for 2024-2026).
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pandas as pd

# Setup path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tezaver.data.binance_client import BinanceClient
from tezaver.core.config import DEFAULT_COINS, DEFAULT_HISTORY_TIMEFRAMES
from tezaver.data.history_service import save_history, load_existing_history, symbol_to_ccxt_pair, timeframe_to_ms
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def fetch_chunk(client, symbol, tf, start_ts, end_ts):
    """Fetches records between two timestamps."""
    all_records = []
    cursor = start_ts
    tf_ms = timeframe_to_ms(tf)
    pair = symbol_to_ccxt_pair(symbol)
    
    while cursor < end_ts:
        try:
            records = client.fetch_ohlcv(symbol, tf, since=cursor, limit=1000)
            if not records: break
            
            all_records.extend(records)
            last_ts = records[-1].timestamp
            cursor = int(last_ts + tf_ms)
            
            if cursor >= end_ts: break
            time.sleep(0.2)
            print(".", end="", flush=True)
        except Exception as e:
            logger.error(f"Error fetching chunk: {e}")
            break
    print()
    
    data = [{"timestamp": r.timestamp, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume} for r in all_records]
    df = pd.DataFrame(data)
    if not df.empty:
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df

def sync_symbol_tf(client, symbol, tf, target_days):
    target_start_dt = datetime.now(timezone.utc) - timedelta(days=target_days)
    target_start_ts = int(target_start_dt.timestamp() * 1000)
    target_end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    existing_df = load_existing_history(symbol, tf)
    
    if existing_df is None or existing_df.empty:
        logger.info(f"  No existing data for {symbol} {tf}. Filling from scratch...")
        new_df = fetch_chunk(client, symbol, tf, target_start_ts, target_end_ts)
        if not new_df.empty:
            save_history(symbol, tf, new_df)
        return

    min_ts = existing_df["timestamp"].min()
    max_ts = existing_df["timestamp"].max()
    
    # 1. Fill Prefix Gap (Missing older data)
    prefix_df = pd.DataFrame()
    if min_ts > (target_start_ts + timeframe_to_ms(tf) * 10): # 10 bars margin
        logger.info(f"  Missing older data for {symbol} {tf}. Fetching prefix...")
        prefix_df = fetch_chunk(client, symbol, tf, target_start_ts, min_ts - 1)
    
    # 2. Fill Suffix Gap (Missing newer data)
    suffix_df = pd.DataFrame()
    if max_ts < (target_end_ts - timeframe_to_ms(tf) * 2): # 2 bars margin
        logger.info(f"  Missing newer data for {symbol} {tf}. Fetching suffix...")
        suffix_df = fetch_chunk(client, symbol, tf, max_ts + 1, target_end_ts)
        
    if not prefix_df.empty or not suffix_df.empty:
        df_all = pd.concat([prefix_df, existing_df, suffix_df], ignore_index=True)
        df_all = df_all.drop_duplicates(subset=["timestamp"], keep="last")
        df_all = df_all.sort_values("timestamp").reset_index(drop=True)
        # Trim older than target just in case
        df_all = df_all[df_all["timestamp"] >= target_start_ts]
        save_history(symbol, tf, df_all)
        logger.info(f"  Merged gaps. Total bars: {len(df_all)}")
    else:
        logger.info(f"  {symbol} {tf} already has full target range.")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=800)
    parser.add_argument("--tf", type=str, default=None, help="Specific timeframe (e.g. 5m, 15m). If None, uses config defaults.")
    parser.add_argument("--symbol", type=str, default=None, help="Specific symbol. If None, uses all config coins.")
    args = parser.parse_args()

    client = BinanceClient()
    logger.info(f"Starting Gap Sync (Target: {args.days} days)")
    
    symbols = [args.symbol] if args.symbol else DEFAULT_COINS
    timeframes = [args.tf] if args.tf else DEFAULT_HISTORY_TIMEFRAMES
    
    logger.info(f"Syncing {len(symbols)} symbols across {timeframes} timeframes.")

    for symbol in symbols:
        logger.info(f"Processing {symbol}...")
        for tf in timeframes:
            try:
                sync_symbol_tf(client, symbol, tf, args.days)
            except Exception as e:
                logger.error(f"Failed {symbol} {tf}: {e}")
        time.sleep(0.5)

if __name__ == "__main__":
    main()
