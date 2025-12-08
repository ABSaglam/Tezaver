"""
Script to run trend & level build manually.
Usage: python src/tezaver/levels/run_trend_levels_build.py
"""

import sys
from pathlib import Path

# src/tezaver/levels/run_trend_levels_build.py
# parents[0] = .../src/tezaver/levels
# parents[1] = .../src/tezaver
# parents[2] = .../src
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tezaver.levels.trend_levels_engine import bulk_build_levels
from tezaver.core.config import DEFAULT_COINS, DEFAULT_LEVEL_TIMEFRAMES
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main() -> None:
    logger.info("Starting trend & level build...")
    logger.info(f"Coins: {DEFAULT_COINS}")
    logger.info(f"Timeframes: {DEFAULT_LEVEL_TIMEFRAMES}")
    
    bulk_build_levels(DEFAULT_COINS, DEFAULT_LEVEL_TIMEFRAMES)
    
    logger.info("Trend & level build completed.")

if __name__ == "__main__":
    main()
