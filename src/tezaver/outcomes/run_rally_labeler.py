"""
Script to run rally labeling manually.
Usage: python src/tezaver/outcomes/run_rally_labeler.py
"""

import sys
from pathlib import Path

# Add src directory to sys.path so that 'tezaver' can be imported
# This file is at: src/tezaver/outcomes/run_rally_labeler.py
# parents[0] = .../src/tezaver/outcomes
# parents[1] = .../src/tezaver
# parents[2] = .../src
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tezaver.outcomes.rally_labeler import bulk_label_snapshots
from tezaver.core.config import DEFAULT_COINS, DEFAULT_SNAPSHOT_BASE_TFS
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main() -> None:
    logger.info("Starting bulk rally labelling...")
    logger.info(f"Coins: {DEFAULT_COINS}")
    logger.info(f"Timeframes: {DEFAULT_SNAPSHOT_BASE_TFS}")
    
    bulk_label_snapshots(DEFAULT_COINS, DEFAULT_SNAPSHOT_BASE_TFS)
    
    logger.info("Rally labelling completed.")

if __name__ == "__main__":
    main()
