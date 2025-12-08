"""
Tezaver Sim v1.5 - Promotion Export CLI
=======================================

Command line interface to run strategy promotion logic (Sim v1.5)
and export results to JSON.

Usage:
    python src/tezaver/sim/run_sim_promotion_export.py --symbol BTCUSDT
    python src/tezaver/sim/run_sim_promotion_export.py --all-symbols
"""

import argparse
import sys
import json
from typing import List

# Ensure src is in path
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[3]))

from tezaver.core.logging_utils import get_logger
from tezaver.core.config import DEFAULT_COINS
from tezaver.core.coin_cell_paths import get_coin_profile_dir
from tezaver.sim.sim_promotion import (
    compute_promotion_for_symbol,
    save_strategy_promotion,
    StrategyPromotionConfig
)

logger = get_logger(__name__)

def load_affinity_data(symbol: str) -> dict:
    """Load sim_affinity.json for symbol."""
    path = get_coin_profile_dir(symbol) / "sim_affinity.json"
    if not path.exists():
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def process_symbol(symbol: str) -> bool:
    """Run promotion logic for a single symbol."""
    logger.info(f"Processing promotion for {symbol}...")
    
    # 1. Load affinity data (Source of Truth for Sim v1.3+)
    affinity = load_affinity_data(symbol)
    if not affinity or 'presets' not in affinity:
        logger.warning(f"No affinity data found for {symbol}. Skipping.")
        return False
        
    # 2. Compute Promotion
    # We pass empty scoreboard_data because sim_affinity.json already has the metrics we need.
    summary = compute_promotion_for_symbol(
        symbol=symbol,
        affinity_data=affinity,
        scoreboard_data={}, 
        config=StrategyPromotionConfig() # Use defaults
    )
    
    # 3. Save
    save_strategy_promotion(summary)
    
    # Summary Log
    approved = sum(1 for s in summary.strategies.values() if s.status == "APPROVED")
    candidate = sum(1 for s in summary.strategies.values() if s.status == "CANDIDATE")
    rejected = sum(1 for s in summary.strategies.values() if s.status == "REJECTED")
    
    print(f"[{symbol}] Promotion: APPROVED={approved}, CANDIDATE={candidate}, REJECTED={rejected}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Tezaver Sim v1.5 Promotion Export")
    parser.add_argument("--symbol", type=str, help="Specific symbol to process")
    parser.add_argument("--all-symbols", action="store_true", help="Process all default symbols")
    
    args = parser.parse_args()
    
    if args.symbol:
        process_symbol(args.symbol)
    elif args.all_symbols:
        count = 0
        for symbol in DEFAULT_COINS:
            if process_symbol(symbol):
                count += 1
        print(f"Finished. Processed {count}/{len(DEFAULT_COINS)} symbols.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
