
import logging
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))

from tezaver.core.logging_utils import init_logging
from tezaver.smyrna.cipher_generator import CipherGenerator

def main():
    init_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting BALANCED Cipher Generation...")
    
    # Initialize Generator
    generator = CipherGenerator(algorithm="ensemble")
    
    try:
        # Generate Cipher for DIAMOND GRIND Rallies (Approved)
        # Filters match the user's request
        cipher = generator.generate_cipher(
            tier="DIAMOND",
            archetype="GRIND", 
            coin_class=None,     # ANY
            timeframe="15m"
        )
        
        logger.info("\n✅ SUCCESS: Cipher Generated!")
        logger.info(f"Cipher ID: {cipher['cipher_id']}")
        logger.info(f"Features: {cipher['entry_rules']['selected_features']}")
        
        # Save ID to a temp file for backtest script to pick up? 
        # Or just user can copy paste.
        
    except Exception as e:
        logger.error(f"Failed to generate cipher: {e}")
        raise

if __name__ == "__main__":
    main()
