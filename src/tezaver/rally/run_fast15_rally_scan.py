"""
CLI script to run Fast15 Rally Scanner.

Usage:
    # Single symbol
    python src/tezaver/rally/run_fast15_rally_scan.py --symbol BTCUSDT
    
    # All symbols from config
    python src/tezaver/rally/run_fast15_rally_scan.py --all-symbols
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tezaver.rally.fast15_rally_scanner import run_fast15_scan_for_symbol
from tezaver.core.config import DEFAULT_COINS
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Fast15 Rally Scanner - detects rapid price movements in 15m timeframe"
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to scan (e.g., BTCUSDT)"
    )
    group.add_argument(
        "--all-symbols",
        action="store_true",
        help="Scan all symbols from config"
    )
    
    args = parser.parse_args()
    
    if args.symbol:
        symbols = [args.symbol]
    else:
        symbols = DEFAULT_COINS
    
    logger.info("=" * 60)
    logger.info("FAST15 RALLY SCANNER")
    logger.info("=" * 60)
    logger.info(f"Scanning {len(symbols)} symbol(s)...")
    
    results = []
    skipped = []
    
    for symbol in symbols:
        logger.info(f"\n>>> Processing {symbol}...")
        
        try:
            result = run_fast15_scan_for_symbol(symbol)
            results.append(result)
            
            logger.info(f"✓ {symbol}: {result.num_events_total} events found")
            if result.num_events_by_bucket:
                logger.info(f"  Buckets: {result.num_events_by_bucket}")
        
        except FileNotFoundError as e:
            logger.warning(f"✗ {symbol}: 15m features not found, skipping")
            skipped.append(symbol)
        
        except Exception as e:
            logger.error(f"✗ {symbol}: Error during scan: {e}", exc_info=True)
            skipped.append(symbol)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SCAN COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Successfully scanned: {len(results)}/{len(symbols)} symbols")
    
    if results:
        total_events = sum(r.num_events_total for r in results)
        logger.info(f"Total events detected: {total_events}")
        
        # Aggregate bucket counts
        aggregate_buckets = {}
        for r in results:
            for bucket, count in r.num_events_by_bucket.items():
                aggregate_buckets[bucket] = aggregate_buckets.get(bucket, 0) + count
        
        if aggregate_buckets:
            logger.info("Aggregate bucket distribution:")
            for bucket, count in sorted(aggregate_buckets.items()):
                logger.info(f"  {bucket}: {count}")
    
    if skipped:
        logger.warning(f"Skipped {len(skipped)} symbols (missing data or errors):")
        logger.warning(f"  {', '.join(skipped)}")
    
    logger.info("\nOutputs saved to:")
    logger.info("  - library/fast15_rallies/{SYMBOL}/fast15_rallies.parquet")
    logger.info("  - data/coin_profiles/{SYMBOL}/fast15_rallies_summary.json")


if __name__ == "__main__":
    main()
