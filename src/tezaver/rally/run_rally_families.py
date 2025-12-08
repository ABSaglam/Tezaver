import sys
import os
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.rally.family_engine import bulk_build_rally_families
from tezaver.core.config import DEFAULT_COINS, DEFAULT_SNAPSHOT_BASE_TFS
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    logger.info("=== Tezaver Rally Family Builder ===")
    logger.info(f"Coins: {DEFAULT_COINS}")
    logger.info(f"Base Timeframes: {DEFAULT_SNAPSHOT_BASE_TFS}")
    
    bulk_build_rally_families(DEFAULT_COINS, DEFAULT_SNAPSHOT_BASE_TFS)
    
    logger.info("=== Rally Family Build Complete ===")

if __name__ == "__main__":
    main()
