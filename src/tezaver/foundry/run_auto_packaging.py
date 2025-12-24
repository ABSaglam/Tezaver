import argparse
import sys
from pathlib import Path
# from tqdm import tqdm

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tezaver.foundry.packaging_v1 import package_symbol_timeframe
from tezaver.core.config import DEFAULT_COINS
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Tezaver Auto-Packager")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbol", type=str, help="Specific symbol to package")
    group.add_argument("--all-symbols", action="store_true", help="Package all symbols")
    
    parser.add_argument("--limit", type=int, default=0, help="Total limit per symbol/tf (safety cap). Use 0 for unlimited.")
    parser.add_argument("--limit-per-tier", type=int, default=3, help="Max bundles PER TIER per symbol/tf (default: 3).")
    parser.add_argument("--clean", action="store_true", help="Clean output directory before running.")
    parser.add_argument("--output", type=str, default=".tezaver_matrix/approved_bundles_v1", help="Output directory root")
    
    args = parser.parse_args()
    
    if args.clean:
        import shutil
        out_path = Path(args.output)
        if out_path.exists():
            logger.info(f"Cleaning output directory: {out_path}")
            shutil.rmtree(out_path)
            out_path.mkdir(parents=True, exist_ok=True)
    
    if args.symbol:
        symbols = [args.symbol]
    else:
        symbols = DEFAULT_COINS
    
    timeframes = ["15m", "1h", "4h"]
    limit_val = None if args.limit == 0 else args.limit
    
    logger.info("=" * 60)
    logger.info(f"AUTO-PACKAGER STARTING")
    logger.info(f"Symbols: {len(symbols)}")
    logger.info(f"Limit Per Tier: {args.limit_per_tier}")
    logger.info("=" * 60)
    
    total_bundles = 0
    
    for symbol in symbols:
        logger.info(f"[Processing {symbol}]")
        for tf in timeframes:
            try:
                bundles = package_symbol_timeframe(
                    symbol=symbol,
                    timeframe=tf,
                    limit=limit_val,
                    limit_per_tier=args.limit_per_tier,
                    output_root=args.output
                )
                if bundles:
                    logger.info(f"  > {tf}: Created {len(bundles)} bundles.")
                    total_bundles += len(bundles)
                else:
                    pass
                    # logger.info(f"  > {tf}: No approved items or failed.")
            except Exception as e:
                logger.error(f"  Failed {symbol} {tf}: {e}")
                
    logger.info("=" * 60)
    logger.info(f"JOB COMPLETE. Total Bundles Created: {total_bundles}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
