"""
History Service for Tezaver Mac.
Handles fetching, saving, and updating historical OHLCV data.
"""

import pandas as pd
from typing import List, Optional
from datetime import datetime, timezone
import sys
from pathlib import Path

# Adjust path to import sibling modules if necessary, though absolute imports are preferred
# Assuming standard structure, these imports should work if run from root or as module
from tezaver.data.binance_client import BinanceClient
from tezaver.data import timeframe_utils
from tezaver.core import coin_cell_paths

from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def symbol_to_ccxt_pair(symbol: str) -> str:
    """
    Converts Tezaver symbol (BTCUSDT) to CCXT pair (BTC/USDT).
    Currently only supports USDT pairs.
    """
    if not symbol.endswith("USDT"):
        raise ValueError(f"Unsupported symbol format: {symbol}. Only USDT pairs are supported.")
    
    base = symbol[:-4]
    return f"{base}/USDT"

def fetch_ohlcv_df(symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
    """
    Fetches OHLCV data and returns it as a DataFrame.
    Adds a 'datetime' column converted from timestamp.
    """
    client = BinanceClient()
    pair = symbol_to_ccxt_pair(symbol)
    
    records = client.fetch_ohlcv(pair, timeframe, limit=limit)
    
    data = [
        {
            "timestamp": r.timestamp,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume
        }
        for r in records
    ]
    
    df = pd.DataFrame(data)
    if not df.empty:
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        
    return df

def load_existing_history(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Loads existing history from Parquet file.
    Returns None if file does not exist.
    """
    file_path = coin_cell_paths.get_history_file(symbol, timeframe)
    
    if not file_path.exists():
        return None
        
    try:
        df = pd.read_parquet(file_path)
        return df
    except Exception as e:
        logger.error(f"Error loading history for {symbol} {timeframe}: {e}", exc_info=True)
        return None

def save_history(symbol: str, timeframe: str, df: pd.DataFrame) -> None:
    """
    Saves DataFrame to Parquet file.
    """
    file_path = coin_cell_paths.get_history_file(symbol, timeframe)
    # Ensure directory exists (get_history_file doesn't create it, but get_coin_data_dir does)
    # Let's double check parent dir existence
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
    df.to_parquet(file_path, index=False)

import time
from datetime import datetime, timezone, timedelta

def timeframe_to_ms(tf: str) -> int:
    """Simple timeframe to milliseconds converter."""
    if tf == "1m": return 60 * 1000
    if tf == "5m": return 5 * 60 * 1000
    if tf == "15m": return 15 * 60 * 1000
    if tf == "1h": return 60 * 60 * 1000
    if tf == "4h": return 4 * 60 * 60 * 1000
    if tf == "1d": return 24 * 60 * 60 * 1000
    if tf == "1w": return 7 * 24 * 60 * 60 * 1000
    return 60 * 1000 # Default 1m

def fetch_backfill_history(symbol: str, timeframe: str, days: int = 730) -> pd.DataFrame:
    """
    Fetches historical data for the last N days using proper pagination.
    """
    client = BinanceClient()
    start_dt = datetime.now() - timedelta(days=days)
    cursor = int(start_dt.timestamp() * 1000)
    
    logger.info(f"Starting backfill for {symbol} {timeframe} (Last {days} days)...")
    
    all_records = []
    tf_ms = timeframe_to_ms(timeframe)
    pair = symbol_to_ccxt_pair(symbol)
    
    while True:
        try:
            records = client.fetch_ohlcv(pair, timeframe, since=cursor, limit=1000)
            if not records:
                break
                
            all_records.extend(records)
            last_ts = records[-1].timestamp
            cursor = int(last_ts + tf_ms)
            
            # Stop if reached now
            if cursor > time.time() * 1000:
                break
                
            time.sleep(0.2) # Rate limit safety
        except Exception as e:
            logger.error(f"Backfill error {symbol} {timeframe}: {e}")
            break
            
    # Convert
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
        df = df.drop_duplicates(subset=["timestamp"], keep="last")
        df = df.sort_values("timestamp").reset_index(drop=True)
        
    return df

def update_history(symbol: str, timeframe: str, max_limit: int = 10000) -> pd.DataFrame:
    """
    Updates history for a coin.
    If no history exists, performs a 2-year backfill.
    If history exists, incrementally updates.
    """
    existing_df = load_existing_history(symbol, timeframe)
    
    # --- SHALLOW HISTORY CHECK & REPAIR ---
    # User wants 2 years (730 days). If existing file is only 30 days deep, we must backfill.
    target_days = 730
    # Tolerance: If we have at least 700 days, consider it fine to avoid constant redownload on edge cases
    # Just check if start time is significantly newer than 2 years ago
    two_years_ms = 730 * 24 * 60 * 60 * 1000
    now_ms = time.time() * 1000
    target_start_ts = now_ms - two_years_ms
    
    should_repair = False
    if existing_df is not None and not existing_df.empty:
        min_ts = existing_df["timestamp"].min()
        # If min_ts is newer than target_start by more than 30 days, we assume it's incomplete
        # (e.g. user has 30 days, but wants 730. 30 days start is way newer than 730 days start)
        if min_ts > (target_start_ts + 30 * 24 * 60 * 60 * 1000):
             # Check if coin is actually new (don't repair if coin didn't exist 2 years ago)
             # Hard to know without metadata, but fetch_backfill_history handles empty starts gracefully usually?
             # Let's assume we should try.
             should_repair = True
             
    if should_repair:
        logger.info(f"Detected shallow history for {symbol} {timeframe}. Repairing (Target 730 days)...")
        repair_df = fetch_backfill_history(symbol, timeframe, days=730)
        
        if not repair_df.empty:
            # Merge with existing
            if existing_df is not None:
                existing_df = pd.concat([repair_df, existing_df], ignore_index=True)
                existing_df = existing_df.drop_duplicates(subset=["timestamp"], keep="last")
                existing_df = existing_df.sort_values("timestamp").reset_index(drop=True)
            else:
                existing_df = repair_df
                
            save_history(symbol, timeframe, existing_df)
            logger.info("Repair complete. Merged deep history.")

    # --- END REPAIR LOGIC ---
    
    if existing_df is None or existing_df.empty:
        # Fetch fresh with smart backfill
        logger.info(f"Missing history for {symbol} {timeframe}. Starting 2-year backfill...")
        new_df = fetch_backfill_history(symbol, timeframe, days=730)
        
        if not new_df.empty:
            save_history(symbol, timeframe, new_df)
            logger.info(f"Backfill complete: {len(new_df)} bars saved.")
        else:
            logger.warning(f"Backfill returned no data for {symbol} {timeframe}.")
            
        return new_df
    else:
        # Fetch since last timestamp
        last_ts = existing_df["timestamp"].max()
        since = int(last_ts) + 1
        
        # logger.info(f"Updating history for {symbol} {timeframe} since {since}...")
        
        client = BinanceClient()
        pair = symbol_to_ccxt_pair(symbol)
        
        # Incremental fetch
        records = client.fetch_ohlcv(pair, timeframe, since=since, limit=max_limit)
        
        if not records:
            # logger.info(f"No new data for {symbol} {timeframe}.")
            return existing_df
            
        data = [
            {
                "timestamp": r.timestamp,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume
            }
            for r in records
        ]
        
        new_part_df = pd.DataFrame(data)
        if not new_part_df.empty:
            new_part_df["datetime"] = pd.to_datetime(new_part_df["timestamp"], unit="ms", utc=True)
            
            # Merge
            df_all = pd.concat([existing_df, new_part_df], ignore_index=True)
            df_all = df_all.drop_duplicates(subset=["timestamp"], keep="last")
            df_all = df_all.sort_values("timestamp").reset_index(drop=True)
            
            save_history(symbol, timeframe, df_all)
            logger.info(f"Updated {symbol} {timeframe}: +{len(new_part_df)} bars.")
            return df_all
        
        return existing_df

def bulk_update_history(symbols: List[str], timeframes: List[str]) -> None:
    """
    Updates history for multiple coins and timeframes.
    """
    for symbol in symbols:
        for tf in timeframes:
            try:
                update_history(symbol, tf)
            except Exception as e:
                logger.error(f"Failed to update {symbol} {tf}: {e}", exc_info=True)
                continue
