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

from tezaver.core.config import DEFAULT_COINS
from tezaver.core.logging_utils import get_logger
from tezaver.rally.time_labs_scanner import (
    run_1h_rally_scan_for_symbol,
    run_4h_rally_scan_for_symbol
)

logger = get_logger(__name__)

def run_for_symbol(symbol: str, tf: str):
    """Dispatch to correct scanner function."""
    try:
        if tf == "1h":
            result = run_1h_rally_scan_for_symbol(symbol)
        elif tf == "4h":
            result = run_4h_rally_scan_for_symbol(symbol)
        else:
            logger.error(f"Unknown timeframe: {tf}")
            return
            
        logger.info(f"Scan complete for {symbol} ({tf}): {result.num_events_total} events found.")
        
    except Exception as e:
        logger.error(f"Failed to run {tf} scan for {symbol}: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="Tezaver Time-Labs Scan Runner")
    parser.add_argument("--tf", type=str, required=True, choices=["1h", "4h"], help="Timeframe to scan (1h or 4h)")
    
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
        
    for sym in symbols_to_scan:
        run_for_symbol(sym, args.tf)
        
    logger.info("Time-Labs Scan Job Completed.")


if __name__ == "__main__":
    main()
