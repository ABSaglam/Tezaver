"""
CLI Script to Generate Sim v1.3 Strategy Affinity Profiles
==========================================================

Usage:
    python src/tezaver/sim/run_sim_affinity_export.py --symbol BTCUSDT
    python src/tezaver/sim/run_sim_affinity_export.py --all-symbols
"""

import argparse
import sys
import logging
from typing import List

# Setup path if running as script
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tezaver.sim.sim_scoreboard import generate_affinity_for_symbol
from tezaver.core.config import DEFAULT_COINS
from tezaver.core.logging_utils import init_logging

logger = logging.getLogger("SimAffinityCLI")

def main():
    parser = argparse.ArgumentParser(description="Tezaver Sim v1.3 Affinity Exporter")
    parser.add_argument("--symbol", type=str, help="Specific symbol to process")
    parser.add_argument("--all-symbols", action="store_true", help="Process all registered symbols")
    
    args = parser.parse_args()
    init_logging()
    
    symbols_to_process = []
    
    if args.symbol:
        symbols_to_process.append(args.symbol)
    elif args.all_symbols:
        symbols_to_process = DEFAULT_COINS
    else:
        print("Please specify --symbol or --all-symbols")
        return

    logger.info(f"Starting Affinity Export for {len(symbols_to_process)} symbols...")
    
    results = []
    for sym in symbols_to_process:
        try:
            logger.info(f"Processing {sym}...")
            summary = generate_affinity_for_symbol(sym)
            
            best_id = summary.best_overall.preset_id if summary.best_overall else "None"
            score = summary.best_overall.affinity_score if summary.best_overall else 0.0
            
            logger.info(f"  -> Best: {best_id} (Score: {score})")
            results.append((sym, best_id, score))
            
        except Exception as e:
            logger.error(f"Failed to process {sym}: {e}")
            
    logger.info("Done.")
    
if __name__ == "__main__":
    main()
