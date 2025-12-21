import argparse
import sys
import types

# MACX-2050: Global dummy dotenv mock to avoid ModuleNotFoundError in dependencies (config.py etc.)
try:
    import dotenv
except ImportError:
    dummy_dotenv = types.ModuleType('dotenv')
    dummy_dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules['dotenv'] = dummy_dotenv

import pandas as pd
import json
from pathlib import Path
from tezaver.core.logging_utils import get_logger
from .story_builder import RallyStoryBuilder
from .bundle_exporter import CandidateBundleExporter
from .story_compiler import StoryCompiler

logger = get_logger(__name__)

def run_export(symbol: str, timeframe: str, limit: int = 5, fail_threshold: float = 0.99, warn_threshold: float = 0.80):
    """
    Main export orchestration logic.
    MACX-2011, MACX-2012, MACX-2013
    """
    logger.info(f"🚀 Starting CandidateBundle v1.1.1 export for {symbol} ({timeframe})")
    
    # Paths (unchanged)
    project_root = Path("/Users/alisaglam/TezaverMac")
    data_dir = project_root / "data"
    profile_dir = data_dir / "coin_profiles" / symbol
    cell_dir = project_root / "coin_cells" / symbol / "data"
    
    # Files (unchanged paths)
    fast15_path = project_root / "library" / "fast15_rallies" / symbol / "fast15_rallies.parquet"
    patterns_path = project_root / "library" / "patterns" / symbol / "snapshots_labeled_1h.parquet"
    history_path = cell_dir / f"history_{timeframe}.parquet"
    
    levels_path = profile_dir / "levels_1h.json"
    regime_path = profile_dir / "regime_profile.json"
    shock_path = profile_dir / "shock_profile.json"
    p_stats_path = profile_dir / "pattern_stats.json"
    families_path = profile_dir / "rally_families.json"

    # Load Data (unchanged loading)
    logger.info("📦 Loading source data...")
    events_df = pd.read_parquet(fast15_path)
    patterns_df = pd.read_parquet(patterns_path)
    history_df = pd.read_parquet(history_path)
    
    with open(levels_path) as f: levels = json.load(f)
    with open(regime_path) as f: regime = json.load(f)
    with open(shock_path) as f: shock = json.load(f)
    with open(p_stats_path) as f: p_stats = json.load(f)
    with open(families_path) as f: families = json.load(f)

    # Config (MACX-2013)
    config = {
        "sl_atr_k": 1.5, 
        "version": "v1.1.1", 
        "min_trigger_resolve_rate": fail_threshold,
        "warn_join_coverage": warn_threshold
    }
    
    # Builders & Compilers
    builder = RallyStoryBuilder(config)
    exporter = CandidateBundleExporter(project_root / "out" / "matrix_candidates")
    compiler = StoryCompiler()
    
    # Process Stories
    stories = []
    processed_count = 0
    for _, row in events_df.head(limit).iterrows():
        try:
            story = builder.build_story(
                symbol=symbol,
                event_row=row,
                history_df=history_df,
                patterns_df=patterns_df,
                levels=levels,
                regime=regime,
                shock=shock,
                pattern_stats=p_stats,
                families=families
            )
            stories.append(story)
            processed_count += 1
        except Exception as e:
            logger.warning(f"⚠️ Failed to build story for {row.get('event_time')}: {e}")

    # MACX-2012/2013: Metrikler ve Katı Eşik Kontrolü
    metrics = builder.get_metrics()
    resolve_rate = metrics['trigger_resolve_rate']
    join_cov = metrics['join_coverage']
    
    logger.info(f"📊 Join Coverage: {join_cov*100:.2f}%")
    logger.info(f"📊 Trigger Resolve Rate: {resolve_rate*100:.2f}% ({metrics['join_matched_count']} join + {metrics['fallback_used_count']} fallback)")
    
    # 1. Hard Lock: Resolve Rate
    if resolve_rate < fail_threshold:
        logger.error(f"❌ FAIL: Trigger resolve rate ({resolve_rate:.2f}) is below mandatory threshold ({fail_threshold:.2f}). Aborting.")
        sys.exit(1)
        
    # 2. Warning: Join Coverage
    if join_cov < warn_threshold:
        logger.warning(f"⚠️ WARN: Join coverage ({join_cov:.2f}) is below recommended threshold ({warn_threshold:.2f}).")

    # MACX-2040: Compile Summaries
    stories_1h = compiler.compile_summaries(stories, "1h")
    stories_4h = compiler.compile_summaries(stories, "4h")

    # Export (MACX-2014)
    source_files = [fast15_path, patterns_path, history_path, levels_path, regime_path, shock_path, p_stats_path, families_path]
    bundle_dir = exporter.export_bundle(
        symbol, timeframe, stories, source_files, config, 
        metrics=metrics,
        diagnostics=builder.diagnostics_log,
        compiled_stories_1h=stories_1h,
        compiled_stories_4h=stories_4h
    )
    
    logger.info(f"✅ Export completed! {processed_count} stories saved to {bundle_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CandidateBundle v1.1.1 Exporter")
    parser.add_argument("--symbol", type=str, required=True, help="Coin symbol (e.g. BTCUSDT)")
    parser.add_argument("--tf", type=str, default="15m", help="Base timeframe")
    parser.add_argument("--limit", type=int, default=5, help="Limit number of events")
    parser.add_argument("--fail-threshold", type=float, default=0.99, help="Min trigger resolve rate (mandatory)")
    parser.add_argument("--warn-threshold", type=float, default=0.80, help="Min join coverage (recommended)")
    
    args = parser.parse_args()
    run_export(args.symbol, args.tf, args.limit, args.fail_threshold, args.warn_threshold)
