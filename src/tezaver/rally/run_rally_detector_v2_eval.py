"""
Rally Detector v2 Evaluation Runner (CLI)
=========================================

Runs multi-coin calibration for Rally Detector v2 Micro-Booster.
Usage:
    python src/tezaver/rally/run_rally_detector_v2_eval.py --all-defaults
    python src/tezaver/rally/run_rally_detector_v2_eval.py --symbol BTCUSDT

Generates JSON statistics in data/rally_detector_v2_stats/15m/
"""

import argparse
import sys
from typing import List

from tezaver.core.logging_utils import get_logger
from tezaver.rally.rally_detector_v2_eval import run_v2_eval_for_symbol, save_v2_eval_stats

logger = get_logger(__name__)

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

def run_eval_batch(symbols: List[str]):
    """Run evaluation for a list of symbols."""
    print(f"🚀 Starting Rally Detector v2 Evaluation for: {', '.join(symbols)}")
    print("-" * 60)
    
    results = []
    
    for symbol in symbols:
        try:
            print(f"Processing {symbol}...", end=" ", flush=True)
            stats = run_v2_eval_for_symbol(symbol, "15m")
            
            if "error" in stats:
                print(f"❌ Error: {stats['error']}")
                continue
                
            path = save_v2_eval_stats(symbol, stats)
            
            count = stats.get("event_count", 0)
            status_icon = "✅" if count > 0 else "⚠️"
            if count > 400: status_icon = "⚠️ HIGH COUNT"
            
            print(f"{status_icon} (Events: {count}) -> {path.name}")
            results.append(stats)
            
        except Exception as e:
            print(f"❌ Exception: {e}")
            logger.error(f"Eval failed for {symbol}: {e}")
            
    print("-" * 60)
    print("✨ Evaluation Batch Complete")


def main():
    parser = argparse.ArgumentParser(description="Rally Detector v2 Eval Runner")
    parser.add_argument("--symbol", type=str, help="Single symbol to evaluate")
    parser.add_argument("--all-defaults", action="store_true", help="Run for BTC, ETH, BNB, SOL")
    
    args = parser.parse_args()
    
    if args.symbol:
        run_eval_batch([args.symbol])
    elif args.all_defaults:
        run_eval_batch(DEFAULT_SYMBOLS)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
