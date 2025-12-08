"""
Script to run CoinState brain sync manually.
Usage: python src/tezaver/core/run_brain_sync.py
"""

import sys
from pathlib import Path

# Add src directory to sys.path so that 'tezaver' can be imported
# This file is at: src/tezaver/core/run_brain_sync.py
# parents[0] = .../src/tezaver/core
# parents[1] = .../src/tezaver
# parents[2] = .../src
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tezaver.core.brain_sync import sync_all_coinstates
from tezaver.core.config import DEFAULT_COINS, DEFAULT_HISTORY_TIMEFRAMES
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main() -> None:
    logger.info("Starting CoinState brain sync...")
    logger.info(f"Coins: {DEFAULT_COINS}")
    logger.info(f"Timeframes: {DEFAULT_HISTORY_TIMEFRAMES}")
    
    sync_all_coinstates(DEFAULT_COINS, DEFAULT_HISTORY_TIMEFRAMES)
    
    logger.info("CoinState brain sync completed.")

if __name__ == "__main__":
    main()
