import sys
import os
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.wisdom.global_wisdom import (
    build_global_pattern_wisdom,
    build_global_regime_wisdom,
    build_global_shock_wisdom,
)
from tezaver.core.config import DEFAULT_COINS
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    logger.info("=== Tezaver Global Wisdom Builder ===")
    logger.info(f"Coins: {DEFAULT_COINS}")
    
    logger.info("--- Building Global Pattern Wisdom ---")
    build_global_pattern_wisdom()
    
    logger.info("--- Building Global Regime Wisdom ---")
    build_global_regime_wisdom()
    
    logger.info("--- Building Global Shock Wisdom ---")
    build_global_shock_wisdom()
    
    logger.info("=== Global Wisdom Build Complete ===")

if __name__ == "__main__":
    main()
