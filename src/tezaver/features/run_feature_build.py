"""
Script to run feature build manually.
Usage: python src/tezaver/features/run_feature_build.py
"""

import sys
from pathlib import Path

# Add src directory to sys.path so that 'tezaver' can be imported
# This file is at: src/tezaver/features/run_feature_build.py
# parents[0] = .../src/tezaver/features
# parents[1] = .../src/tezaver
# parents[2] = .../src
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tezaver.features.indicator_engine import bulk_build_features
from tezaver.core.config import DEFAULT_COINS, DEFAULT_FEATURE_TIMEFRAMES
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main() -> None:
    logger.info("Starting bulk feature build...")
    logger.info(f"Coins: {DEFAULT_COINS}")
    logger.info(f"Timeframes: {DEFAULT_FEATURE_TIMEFRAMES}")
    
    bulk_build_features(DEFAULT_COINS, DEFAULT_FEATURE_TIMEFRAMES)
    
    logger.info("Feature build completed.")

if __name__ == "__main__":
    main()
