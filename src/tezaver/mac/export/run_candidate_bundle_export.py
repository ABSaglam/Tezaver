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
from .bundle_exporter import BundleExporter
from .story_compiler import StoryCompiler

logger = get_logger(__name__)

def run_export(symbol: str, timeframe: str, limit: int = 5, min_resolve_rate: float = 0.99, warn_join_cov: float = 0.80):
    """
    Main export orchestration logic.
    MACX-2100, MACX-2130, MACX-2140
    """
    logger.info(f"🚀 Starting CandidateBundle v1.1.2 export for {symbol} ({timeframe})")
    
    # Paths
    project_root = Path("/Users/alisaglam/TezaverMac")
    data_dir = project_root / "data"
    profile_dir = data_dir / "coin_profiles" / symbol
    cell_dir = project_root / "coin_cells" / symbol / "data"
    
    # Files
    fast15_path = project_root / "library" / "fast15_rallies" / symbol / "fast15_rallies.parquet"
    patterns_path = project_root / "library" / "patterns" / symbol / "snapshots_labeled_1h.parquet"
    history_path = cell_dir / f"history_{timeframe}.parquet"
    
    levels_path = profile_dir / "levels_1h.json"
    regime_path = profile_dir / "regime_profile.json"
    shock_path = profile_dir / "shock_profile.json"
    p_stats_path = profile_dir / "pattern_stats.json"
    families_path = profile_dir / "rally_families.json"

    # Load Data
    logger.info("📦 Loading source data...")
    events_df = pd.read_parquet(fast15_path)
    patterns_df = pd.read_parquet(patterns_path)
    history_df = pd.read_parquet(history_path)
    
    with open(levels_path) as f: levels = json.load(f)
    with open(regime_path) as f: regime = json.load(f)
    with open(shock_path) as f: shock = json.load(f)
    with open(p_stats_path) as f: p_stats = json.load(f)
    with open(families_path) as f: families = json.load(f)

    # Config
    config = {
        "sl_atr_k": 1.5, 
        "version": "v1.1.2", 
        "min_trigger_resolve_rate": min_resolve_rate,
        "warn_join_coverage": warn_join_cov
    }
    
    # Builders & Exporters
    builder = RallyStoryBuilder(config)
    exporter = BundleExporter(str(project_root / "out" / "matrix_candidates"))
    compiler = StoryCompiler()
    
    # Build stories
    stories = []
    for _, event in events_df.head(limit).iterrows():
        story = builder.build_story(
            symbol=symbol,
            event_row=event,
            history_df=history_df,
            patterns_df=patterns_df,
            levels=levels,
            regime=regime,
            shock=shock,
            pattern_stats=p_stats,
            families=families
        )
        stories.append(story)
        
    # Compile multi-tf stories
    compiled_stories = {
        "summaries_1h": compiler.compile_summaries(stories, "1h"),
        "summaries_4h": compiler.compile_summaries(stories, "4h")
    }
    
    # Fingerprints (Placeholder logic for demo / simplified)
    fingerprints = {
        "data_fingerprint": "mock_data_fp",
        "config_signature": "mock_config_sig"
    }
    
    # MACX-2130: Metrics
    metrics = builder.get_metrics_v2()
    resolve_rate = metrics.get("trigger_resolve_rate", 0)
    join_coverage = metrics.get("join_coverage", 0)
    
    # Threshold checks
    is_failed = False
    if resolve_rate < min_resolve_rate:
        logger.error(f"❌ FAIL: Trigger resolve rate ({resolve_rate:.2%}) is below mandatory threshold ({min_resolve_rate:.2%}).")
        is_failed = True
    elif join_coverage < warn_join_cov:
        logger.warning(f"⚠️ WARN: Join coverage ({join_coverage:.2%}) is below recommended threshold ({warn_join_cov:.2%}).")

    # MACX-2140: Export bundle
    export_path = exporter.export_bundle(
        symbol=symbol,
        tf=timeframe,
        stories=stories,
        compiled_stories=compiled_stories,
        metrics=metrics,
        diagnostics=builder.diagnostics_log,
        fingerprints=fingerprints,
        is_failed=is_failed
    )
    
    if is_failed:
        logger.error(f"🚨 Bundle written to FAIL directory: {export_path}")
        sys.exit(1)
    else:
        logger.info(f"✅ Successfully exported CandidateBundle to: {export_path}")
        logger.info(f"📊 Metrics: Resolve Rate = {resolve_rate:.2%}, Join Coverage = {join_coverage:.2%}")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CandidateBundle v1.1.2 Exporter")
    parser.add_argument("--symbol", type=str, required=True, help="Coin symbol (e.g. BTCUSDT)")
    parser.add_argument("--tf", type=str, default="15m", help="Base timeframe")
    parser.add_argument("--limit", type=int, default=5, help="Limit number of events")
    parser.add_argument("--fail-threshold", type=float, default=0.99, help="Min trigger resolve rate (mandatory)")
    parser.add_argument("--warn-threshold", type=float, default=0.80, help="Min join coverage (recommended)")
    
    args = parser.parse_args()
    run_export(args.symbol, args.tf, args.limit, args.fail_threshold, args.warn_threshold)
