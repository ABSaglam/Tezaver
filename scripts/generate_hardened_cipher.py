"""
Generate Hardened Cipher (Active Learning)
==========================================

This script generates a new Master Cipher using "Hard Negatives" mined from 
previous backtest failures.

Usage:
    python scripts/generate_hardened_cipher.py
"""

from pathlib import Path
import sys

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))

from tezaver.core.logging_utils import init_logging, get_logger
from tezaver.smyrna.cipher_generator import CipherGenerator

init_logging()
logger = get_logger(__name__)

HARD_NEGATIVES_PATH = project_root / ".tezaver_matrix" / "vault" / "datasets" / "hard_negatives_v1.json"

def main():
    logger.info("Starting Hardened Cipher Generation...")
    
    if not HARD_NEGATIVES_PATH.exists():
        logger.error(f"Hard negatives file not found: {HARD_NEGATIVES_PATH}")
        logger.error("Run 'python scripts/mine_hard_negatives.py' first!")
        return

    generator = CipherGenerator(algorithm="ensemble")
    
    try:
        # Generate Cipher for DIAMOND / GRIND / ANY Class / 15m
        # Incorporating Hard Negatives
        cipher = generator.generate_cipher(
            tier="DIAMOND",
            archetype="GRIND", 
            coin_class="ANY",
            timeframe="15m",
            hard_negatives_path=str(HARD_NEGATIVES_PATH)
        )
        
        logger.info("\n🏆 Hardened Cipher Generated Successfully!")
        logger.info(f"ID: {cipher['cipher_id']}")
        logger.info(f"Features: {cipher['entry_rules']['feature_count']}")
        logger.info(f"Hard Negatives Used: {cipher['training_stats']['hard_negatives']}")
        
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
