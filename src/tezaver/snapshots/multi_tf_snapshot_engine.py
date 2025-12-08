"""
M8: Multi-Timeframe Snapshot Engine.
Enriches single-timeframe snapshots with indicator context from multiple timeframes.

Tezaver Philosophy:
- "We don't just store a single timeframe; we freeze the whole multi-timeframe context of that trigger moment."
"""

import pandas as pd
from typing import List, Dict, Optional
from pathlib import Path
import sys

# Adjust path to allow imports if run directly or as module
from tezaver.snapshots.snapshot_engine import (
    get_symbol_pattern_dir,
    get_snapshot_file,
    load_features,
)
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

# --- Configuration ---
from tezaver.core.config import (
    DEFAULT_SNAPSHOT_BASE_TFS,
    MULTI_TF_MAPPING,
)


# --- Helpers ---

def prepare_feature_view_for_tf(
    symbol: str,
    timeframe: str,
    prefix: Optional[str] = None,
    selected_cols: Optional[List[str]] = None,
) -> Optional[pd.DataFrame]:
    """
    Loads feature parquet for (symbol, timeframe), keeps only needed columns,
    and prefixes them with tf-specific prefix (e.g. 'tf_1h_' or 'tf_4h_').

    Returns a DataFrame with:
        - 'timestamp' column
        - prefixed feature columns

    If file is missing or empty, returns None.
    """
    try:
        df_feat = load_features(symbol, timeframe)
    except FileNotFoundError:
        logger.warning(f"Features not found for {symbol} {timeframe}, skipping context.")
        return None

# ... (omitted unchanged lines)

def build_multi_tf_snapshots_for_symbol(
    symbol: str,
    base_timeframe: str,
) -> pd.DataFrame:
    """
    Builds multi-timeframe snapshots for a given symbol and base timeframe.

    Steps:
    - Load base snapshots from M4 (snapshots_{base_tf}.parquet).
    - For each configured timeframe in MULTI_TF_MAPPING[base_timeframe]:
        - Load its feature view with prefixed columns.
        - Merge using merge_asof on 'timestamp' (backward).
    - Save final table to: library/patterns/{SYMBOL}/snapshots_multi_{base_tf}.parquet
    """
    # 1. Load base snapshots
    snapshot_file = get_snapshot_file(symbol, base_timeframe)
    if not snapshot_file.exists():
        logger.info(f"No base snapshots for {symbol} {base_timeframe}, skipping.")
        return pd.DataFrame()
        
    df_base = pd.read_parquet(snapshot_file)
    
    if df_base.empty:
        return pd.DataFrame()
        
    # Ensure sorted
    df_base = df_base.sort_values("timestamp")
    
    # Add base_timeframe column (Option A)
    df_base["base_timeframe"] = base_timeframe
    
    # 2. Determine context timeframes
    extra_timeframes = MULTI_TF_MAPPING.get(base_timeframe, [])
    if not extra_timeframes:
        logger.warning(f"No multi-TF mapping for base timeframe {base_timeframe}, returning base DF.")
        return df_base
        
    # 3. Merge context
    df_multi = df_base.copy()
    
    for tf in extra_timeframes:
        df_feat = prepare_feature_view_for_tf(symbol, tf)
        
        if df_feat is None:
            continue
            
        # Merge backward: find the feature row at or before the snapshot timestamp
        df_multi = pd.merge_asof(
            df_multi.sort_values("timestamp"),
            df_feat.sort_values("timestamp"),
            on="timestamp",
            direction="backward",
        )
        
    # 4. Finalize
    df_multi = df_multi.sort_values("timestamp").reset_index(drop=True)
    
    # 5. Save
    symbol_dir = get_symbol_pattern_dir(symbol)
    out_file = symbol_dir / f"snapshots_multi_{base_timeframe}.parquet"
    df_multi.to_parquet(out_file, index=False)
    
    return df_multi


def bulk_build_multi_tf_snapshots(
    symbols: List[str],
    base_timeframes: List[str],
) -> None:
    """
    Builds multi-timeframe snapshots for multiple coins and base timeframes.
    """
    for symbol in symbols:
        for base_tf in base_timeframes:
            if base_tf not in MULTI_TF_MAPPING:
                logger.debug(f"Skipping {base_tf} (no mapping defined).")
                continue
                
            logger.info(f"Building multi-TF snapshots for {symbol} {base_tf}...")
            try:
                build_multi_tf_snapshots_for_symbol(symbol, base_tf)
            except Exception as e:
                logger.error(f"Failed to build multi-TF snapshots for {symbol} {base_tf}: {e}", exc_info=True)
                continue
