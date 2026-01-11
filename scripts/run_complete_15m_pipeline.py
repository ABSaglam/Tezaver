#!/usr/bin/env python3
"""
Full 15m Pipeline: Download 15m history + Build Features + Rally Scan
for ALL symbols in coin_cells that are missing 15m data.

Usage:
    source venv/bin/activate && nohup python scripts/run_complete_15m_pipeline.py > logs/complete_15m_pipeline.log 2>&1 &
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tezaver.data.binance_client import BinanceClient
from tezaver.data.history_service import save_history
from tezaver.features.indicator_engine import build_features_for_symbol_timeframe
from tezaver.rally.fast15_rally_scanner import run_fast15_scan_for_symbol
from tezaver.ony.auto_approver import OnyAutoApprover
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def timeframe_to_ms(tf: str) -> int:
    if tf == "15m": return 15 * 60 * 1000
    if tf == "1h": return 60 * 60 * 1000
    if tf == "4h": return 4 * 60 * 60 * 1000
    if tf == "1d": return 24 * 60 * 60 * 1000
    raise ValueError(f"Unknown timeframe: {tf}")


def fetch_history(client, symbol: str, tf: str, start_ts: int):
    """Fetch history from Binance with pagination."""
    all_records = []
    cursor = start_ts
    tf_ms = timeframe_to_ms(tf)
    
    while True:
        try:
            records = client.fetch_ohlcv(symbol, tf, since=cursor, limit=1000)
            if not records:
                break
            all_records.extend(records)
            
            last_ts = records[-1].timestamp
            cursor = int(last_ts + tf_ms)
            
            if cursor > time.time() * 1000:
                break
            
            time.sleep(0.3)  # Rate limit
            
        except Exception as e:
            logger.error(f"Error: {e}")
            break
    
    data = [{"timestamp": r.timestamp, "open": r.open, "high": r.high, 
             "low": r.low, "close": r.close, "volume": r.volume} for r in all_records]
    
    df = pd.DataFrame(data)
    if not df.empty:
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset=["timestamp"], keep="last")
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths

def get_symbols_missing_15m():
    """Get symbols from DEFAULT_COINS missing 15m history."""
    missing = []
    for symbol in DEFAULT_COINS:
        history_15m = coin_cell_paths.get_history_file(symbol, "15m")
        if not history_15m.exists():
            missing.append(symbol)
    return sorted(missing)


def get_symbols_needing_scan():
    """Get symbols with features but no rally scan."""
    fast15_dir = Path("library/fast15_rallies")
    
    with_features = set()
    for symbol in DEFAULT_COINS:
        if (coin_cell_paths.get_coin_data_dir(symbol) / "features_15m.parquet").exists():
            with_features.add(symbol)
    
    scanned = set()
    if fast15_dir.exists():
        for d in fast15_dir.iterdir():
            if d.is_dir() and (d / "fast15_rallies.parquet").exists():
                scanned.add(d.name)
    
    return sorted(with_features - scanned)


def main():
    start_time = datetime.now()
    start_ts = int((datetime.now() - timedelta(days=800)).timestamp() * 1000)
    
    print("=" * 80)
    print("🚀 COMPLETE 15m PIPELINE")
    print("=" * 80)
    print(f"Start: {start_time}")
    
    # Phase 1: Download missing 15m history
    missing_history = get_symbols_missing_15m()
    print(f"\n📥 PHASE 1: 15m History Download")
    print(f"Missing: {len(missing_history)} symbols")
    
    client = BinanceClient()
    download_errors = []
    
    for i, symbol in enumerate(missing_history, 1):
        print(f"  [{i}/{len(missing_history)}] {symbol}...", end=" ", flush=True)
        try:
            # Download 15m, 1h, 4h, 1d
            for tf in ['15m', '1h', '4h', '1d']:
                df = fetch_history(client, symbol, tf, start_ts)
                if not df.empty:
                    save_history(symbol, tf, df)
            print(f"✓")
            time.sleep(0.5)
        except Exception as e:
            print(f"✗ {str(e)[:30]}")
            download_errors.append(symbol)
    
    # Phase 2: Build features for symbols with history but no features
    print(f"\n📊 PHASE 2: Feature Calculation")
    need_features = []
    for symbol in DEFAULT_COINS:
        history = coin_cell_paths.get_history_file(symbol, "15m")
        features = coin_cell_paths.get_coin_data_dir(symbol) / "features_15m.parquet"
        if history.exists() and not features.exists():
            need_features.append(symbol)
    
    print(f"Need features: {len(need_features)}")
    feature_errors = []
    
    for i, symbol in enumerate(sorted(need_features), 1):
        print(f"  [{i}/{len(need_features)}] {symbol}...", end=" ", flush=True)
        try:
            for tf in ['15m', '1h', '4h', '1d']:
                build_features_for_symbol_timeframe(symbol, tf)
            print("✓")
        except Exception as e:
            print(f"✗ {str(e)[:30]}")
            feature_errors.append(symbol)
    
    # Phase 3: Rally scan
    print(f"\n🔍 PHASE 3: Rally Scan")
    need_scan = get_symbols_needing_scan()
    print(f"Need scan: {len(need_scan)}")
    
    approver = OnyAutoApprover()
    scan_results = []
    scan_errors = []
    
    for i, symbol in enumerate(need_scan, 1):
        print(f"  [{i}/{len(need_scan)}] {symbol}...", end=" ", flush=True)
        try:
            result = run_fast15_scan_for_symbol(symbol)
            scan_results.append({'symbol': symbol, 'events': result.num_events_total})
            print(f"✓ {result.num_events_total} rallies")
            try:
                approver.process_symbol(symbol, "15m")
            except:
                pass
        except Exception as e:
            print(f"✗ {str(e)[:30]}")
            scan_errors.append(symbol)
    
    # Summary
    duration = datetime.now() - start_time
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Duration: {duration}")
    print(f"Downloaded: {len(missing_history) - len(download_errors)}/{len(missing_history)}")
    print(f"Features: {len(need_features) - len(feature_errors)}/{len(need_features)}")
    print(f"Scanned: {len(need_scan) - len(scan_errors)}/{len(need_scan)}")
    
    if scan_results:
        total = sum(r['events'] for r in scan_results)
        print(f"New rallies: {total:,}")
    
    print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    main()
