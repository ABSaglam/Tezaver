"""
Script to run pattern stats manually.
Usage: python src/tezaver/wisdom/run_pattern_stats.py
"""

import sys
from pathlib import Path

# Add src directory to sys.path so that 'tezaver' can be imported
# This file is at: src/tezaver/wisdom/run_pattern_stats.py
# parents[0] = .../src/tezaver/wisdom
# parents[1] = .../src/tezaver
# parents[2] = .../src
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tezaver.wisdom.pattern_stats import bulk_build_wisdom
from tezaver.core.config import DEFAULT_COINS, DEFAULT_SNAPSHOT_BASE_TFS
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main() -> None:
    logger.info("Starting wisdom build...")
    logger.info(f"Coins: {DEFAULT_COINS}")
    logger.info(f"Timeframes: {DEFAULT_SNAPSHOT_BASE_TFS}")
    
    bulk_build_wisdom(DEFAULT_COINS, DEFAULT_SNAPSHOT_BASE_TFS)
    
    logger.info("Wisdom build completed.")

if __name__ == "__main__":
    main()
