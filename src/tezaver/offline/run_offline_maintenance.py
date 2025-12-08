
"""
Offline Maintenance CLI Entry Point
===================================

Runs the Offline Maintenance Pipeline.

Usage:
    python src/tezaver/offline/run_offline_maintenance.py --mode full --all-symbols
    python src/tezaver/offline/run_offline_maintenance.py --mode symbol --symbol ETHUSDT
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[3]
sys.path.append(str(project_root / "src"))

from tezaver.core.logging_utils import get_logger
from tezaver.offline.offline_maintenance import OfflineMaintenanceRunner

logger = get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Tezaver Offline Maintenance Runner")
    parser.add_argument("--mode", type=str, choices=["full", "fast", "symbol"], default="fast",
                       help="Maintenance mode: full (all tasks), fast (essential), symbol (single coin)")
    parser.add_argument("--symbol", type=str, help="Target symbol for 'symbol' mode")
    parser.add_argument("--all-symbols", action="store_true", help="Target all coins for full/fast mode")
    parser.add_argument("--stop-on-first-error", action="store_true", help="Stop pipeline on first task failure")
    
    args = parser.parse_args()
    
    # Validation
    if args.mode == "symbol" and not args.symbol:
        print("❌ Error: --symbol is required for 'symbol' mode.")
        sys.exit(1)
        
    symbols = [args.symbol] if args.symbol else None
    
    # Initialize Runner
    runner = OfflineMaintenanceRunner(mode=args.mode, symbols=symbols)
    
    # Run
    print(f"🔧 Starting Maintenance Pipeline (Mode: {args.mode})...")
    summary = runner.run()
    
    # Report
    print(f"\n✨ Maintenance Completed | Status: {summary.overall_status.upper()}")
    print("-" * 60)
    print(f"{'Task Name':<30} | {'Status':<10} | {'Duration'}")
    print("-" * 60)
    
    for t in summary.tasks:
        ignore_icon = "✅" if t.status == "success" else "❌" if t.status == "failed" else "⚠️"
        print(f"{ignore_icon} {t.name:<27} | {t.status:<10} | {t.duration_sec:.2f}s")
        
    print("-" * 60)
    
    if summary.overall_status == "failed":
        sys.exit(2)
    elif summary.overall_status == "partial":
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
