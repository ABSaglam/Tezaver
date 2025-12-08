"""
Script to run history update manually.
Usage: python src/tezaver/data/run_history_update.py
"""

import sys
from pathlib import Path

# Add src directory to sys.path so that 'tezaver' can be imported
# This file is at: src/tezaver/data/run_history_update.py
# parents[0] = .../src/tezaver/data
# parents[1] = .../src/tezaver
# parents[2] = .../src
project_root = Path(__file__).resolve().parents[2]  # this is the 'src' directory
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tezaver.data.history_service import bulk_update_history
from tezaver.core.config import DEFAULT_COINS, DEFAULT_HISTORY_TIMEFRAMES
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main() -> None:
    logger.info("Starting bulk history update...")
    logger.info(f"Coins: {DEFAULT_COINS}")
    logger.info(f"Timeframes: {DEFAULT_HISTORY_TIMEFRAMES}")
    
    bulk_update_history(DEFAULT_COINS, DEFAULT_HISTORY_TIMEFRAMES)
    
    logger.info("Update completed.")

if __name__ == "__main__":
    main()
