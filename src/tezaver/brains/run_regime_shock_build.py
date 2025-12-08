import sys
import os
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.brains.regime_brain import build_regime_profiles
from tezaver.brains.shock_brain import build_shock_profiles

from tezaver.core.config import DEFAULT_COINS
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    logger.info("=== Tezaver Regime & Shock Brain Builder ===")
    logger.info(f"Coins: {DEFAULT_COINS}")
    
    logger.info("--- Building Regime Profiles ---")
    build_regime_profiles(DEFAULT_COINS, timeframes=["4h", "1d"])
    
    logger.info("--- Building Shock Profiles ---")
    build_shock_profiles(DEFAULT_COINS, timeframes=["1h", "4h"])
    
    logger.info("=== Regime & Shock Build Complete ===")

if __name__ == "__main__":
    main()
