
"""
CLI Script to generating Rally Radar Profiles (Rally Radar v1)
==============================================================

Usage:
    python src/tezaver/rally/run_rally_radar_export.py --symbol BTCUSDT
    python src/tezaver/rally/run_rally_radar_export.py --all-symbols
"""

import sys
import argparse
import time
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[3]
sys.path.append(str(project_root / "src"))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core.logging_utils import get_logger
from tezaver.rally.rally_radar_engine import build_rally_radar_profile, save_rally_radar_profile

logger = get_logger(__name__)

def process_symbol(symbol: str) -> bool:
    """Run Rally Radar analysis for a single symbol."""
    try:
        start_t = time.time()
        
        # Build Profile (Auto-loads Fast15/Time-Labs/SimPromos)
        profile = build_rally_radar_profile(symbol)
        
        # Save
        path = save_rally_radar_profile(symbol, profile)
        
        dur = time.time() - start_t
        
        # Log summary
        status = profile.overall.get("overall_status", "UNKNOWN")
        lane = profile.overall.get("dominant_lane", "NONE")
        
        print(f"✅ {symbol}: Saved to {path.name} ({dur:.2f}s) | Status: {status} | Lane: {lane}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to process {symbol}: {e}", exc_info=True)
        print(f"❌ {symbol}: Error - {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate Rally Radar Profiles")
    parser.add_argument("--symbol", type=str, help="Single coin symbol to process")
    parser.add_argument("--all-symbols", action="store_true", help="Process all default coins")
    
    args = parser.parse_args()
    
    if args.symbol:
        process_symbol(args.symbol.upper())
    elif args.all_symbols:
        print(f"🚀 Starting Rally Radar generation for {len(DEFAULT_COINS)} coins...")
        success_count = 0
        for symbol in DEFAULT_COINS:
            if process_symbol(symbol):
                success_count += 1
        
        print(f"\n✨ Completed! {success_count}/{len(DEFAULT_COINS)} profiles generated successfully.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
