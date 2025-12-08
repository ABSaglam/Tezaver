"""
Tezaver Mac Pipeline Orchestrator (M22)
========================================

Unified entry point for running the entire Tezaver Mac offline pipeline.

Usage:
    python src/tezaver/run_pipeline.py --mode full   # Full pipeline
    python src/tezaver/run_pipeline.py --mode fast   # Brain sync + export only

Modes:
    full: Runs all pipeline steps from data ingestion to export
    fast: Runs only brain sync and bulut export (for quick updates)
"""

import argparse
import sys
from pathlib import Path

# Add src directory to sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from tezaver.core.logging_utils import get_logger

# Import main functions from all pipeline scripts
from tezaver.data.run_history_update import main as run_history_update_main
from tezaver.features.run_feature_build import main as run_feature_build_main
from tezaver.snapshots.run_snapshot_build import main as run_snapshot_build_main
from tezaver.snapshots.run_multi_tf_snapshot_build import main as run_multi_tf_snapshot_build_main
from tezaver.outcomes.run_rally_labeler import main as run_rally_labeler_main
from tezaver.rally.run_rally_families import main as run_rally_families_main
from tezaver.wisdom.run_pattern_stats import main as run_pattern_stats_main
from tezaver.brains.run_regime_shock_build import main as run_regime_shock_build_main
from tezaver.wisdom.run_global_wisdom import main as run_global_wisdom_main
from tezaver.levels.run_trend_levels_build import main as run_trend_levels_build_main
from tezaver.core.run_brain_sync import main as run_brain_sync_main
from tezaver.export.run_bulut_export import main as run_bulut_export_main
from tezaver.backup.run_backup import main as run_backup_main

logger = get_logger(__name__)


def run_full_pipeline() -> None:
    """
    Runs the complete Tezaver Mac pipeline.
    
    Pipeline Steps:
        M2  - History update
        M3  - Feature build
        M4  - Snapshot build
        M8  - Multi-TF snapshot build
        M5  - Rally labelling
        M14 - Rally families
        M6  - Pattern wisdom
        M15 - Regime & Shock brains
        M18 - Global wisdom
        M11-M12 - Levels build
        M7  - CoinState brain sync
        M16 - Bulut export
        M13 - Mini backup
    """
    logger.info("=" * 60)
    logger.info("TEZAVER MAC FULL PIPELINE STARTING")
    logger.info("=" * 60)
    
    try:
        logger.info("Step 1/13: M2 - History update")
        run_history_update_main()
        
        logger.info("Step 2/13: M3 - Feature build")
        run_feature_build_main()
        
        logger.info("Step 3/13: M4 - Snapshot build")
        run_snapshot_build_main()
        
        logger.info("Step 4/13: M8 - Multi-TF snapshot build")
        run_multi_tf_snapshot_build_main()
        
        logger.info("Step 5/13: M5 - Rally labelling")
        run_rally_labeler_main()
        
        logger.info("Step 6/13: M14 - Rally families build")
        run_rally_families_main()
        
        logger.info("Step 7/13: M6 - Pattern wisdom build")
        run_pattern_stats_main()
        
        logger.info("Step 8/13: M15 - Regime & Shock brain build")
        run_regime_shock_build_main()
        
        logger.info("Step 9/13: M18 - Global wisdom build")
        run_global_wisdom_main()
        
        logger.info("Step 10/13: M11-M12 - Levels build")
        run_trend_levels_build_main()
        
        logger.info("Step 11/13: M7 - CoinState brain sync")
        run_brain_sync_main()
        
        logger.info("Step 12/13: M16 - Bulut export")
        run_bulut_export_main()
        
        logger.info("Step 13/13: M13 - Mini backup")
        run_backup_main()
        
        logger.info("=" * 60)
        logger.info("FULL PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Pipeline failed at step: {e}", exc_info=True)
        raise


def run_fast_pipeline() -> None:
    """
    Runs a fast incremental pipeline update.
    
    Fast Pipeline Steps:
        M7  - CoinState brain sync
        M16 - Bulut export
    """
    logger.info("=" * 60)
    logger.info("TEZAVER MAC FAST PIPELINE STARTING")
    logger.info("=" * 60)
    
    try:
        logger.info("Step 1/2: M7 - CoinState brain sync")
        run_brain_sync_main()
        
        logger.info("Step 2/2: M16 - Bulut export")
        run_bulut_export_main()
        
        logger.info("=" * 60)
        logger.info("FAST PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Fast pipeline failed: {e}", exc_info=True)
        raise


def main() -> None:
    """Main entry point for pipeline orchestrator."""
    parser = argparse.ArgumentParser(
        description="Tezaver Mac Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/tezaver/run_pipeline.py --mode full   # Run complete pipeline
  python src/tezaver/run_pipeline.py --mode fast   # Quick brain sync + export
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["full", "fast"],
        default="full",
        help="Pipeline mode: 'full' runs all steps, 'fast' runs only brain sync + export"
    )
    
    args = parser.parse_args()
    
    logger.info(f"Pipeline mode: {args.mode}")
    
    if args.mode == "full":
        run_full_pipeline()
    else:
        run_fast_pipeline()


if __name__ == "__main__":
    main()
