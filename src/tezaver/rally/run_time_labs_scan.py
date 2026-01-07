"""
Time-Labs v1 CLI Runner
=======================

CLI entry point for running 1h and 4h rally scanners.

Usage:
    python src/tezaver/rally/run_time_labs_scan.py --tf 1h --symbol ETHUSDT
    python src/tezaver/rally/run_time_labs_scan.py --tf 4h --all-symbols
"""

import argparse
import sys
from typing import List

from tezaver.core.config import DEFAULT_COINS, TIME_LABS_LOOKAHEAD_BARS, TIME_LABS_MIN_GAIN, TIME_LABS_RALLY_BUCKETS, TIME_LABS_EVENT_GAP
from tezaver.core.logging_utils import get_logger
from tezaver.rally.time_labs_scanner import run_timeframe_rally_scan_for_symbol
from tezaver.ony.auto_approver import OnyAutoApprover

logger = get_logger(__name__)

def run_for_symbol(symbol: str, tf: str):
    """Dispatch to generic scanner function."""
    try:
        if tf not in TIME_LABS_LOOKAHEAD_BARS:
             logger.error(f"Unknown timeframe/config missing: {tf}")
             return

        result = run_timeframe_rally_scan_for_symbol(
            symbol=symbol,
            timeframe=tf,
            lookahead=TIME_LABS_LOOKAHEAD_BARS[tf],
            min_gain=TIME_LABS_MIN_GAIN[tf],
            buckets=TIME_LABS_RALLY_BUCKETS,
            event_gap=TIME_LABS_EVENT_GAP[tf]
        )
            
        logger.info(f"Scan complete for {symbol} ({tf}): {result.num_events_total} events found.")
        
        # --- ONY AUTO-APPROVE ---
        approver = OnyAutoApprover()
        created_count = approver.process_symbol(symbol, tf)
        if created_count > 0:
            logger.info(f"  [ONY] Auto-Approved {created_count} new events.")
        
    except Exception as e:
        logger.error(f"Failed to run {tf} scan for {symbol}: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="Tezaver Time-Labs Scan Runner")
    # Added 1d and 5m support to CLI
    parser.add_argument("--tf", type=str, required=True, choices=["5m", "15m", "1h", "4h", "1d"], help="Timeframe (e.g. 1h, 4h, 1d)")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbol", type=str, help="Specific symbol to scan (e.g. BTCUSDT)")
    group.add_argument("--all-symbols", action="store_true", help="Scan all default coins")
    
    args = parser.parse_args()
    
    logger.info(f"Starting Time-Labs Scan | Timeframe: {args.tf} | "
                f"Target: {'ALL' if args.all_symbols else args.symbol}")
    
    symbols_to_scan = []
    if args.all_symbols:
        symbols_to_scan = DEFAULT_COINS
    else:
        symbols_to_scan = [args.symbol]
        
    for i, sym in enumerate(symbols_to_scan):
        if args.all_symbols and i % 10 == 0:
            print(f"Progress: {i}/{len(symbols_to_scan)}...")
        run_for_symbol(sym, args.tf)
        
    logger.info("Time-Labs Scan Job Completed.")


if __name__ == "__main__":
    main()
