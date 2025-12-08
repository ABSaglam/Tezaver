import sys
import os
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.export.bulut_exporter import bulk_build_bulut_exports
from tezaver.core.config import DEFAULT_COINS
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    logger.info("=== Tezaver Bulut Export Builder ===")
    logger.info(f"Coins: {DEFAULT_COINS}")
    
    bulk_build_bulut_exports(DEFAULT_COINS)
    
    logger.info("=== Bulut Export Complete ===")

if __name__ == "__main__":
    main()
