"""
Rally Labeler for Tezaver Mac.
Analyzes future price action to label snapshots with rally outcomes.

Tezaver Philosophy:
- "Her snapshot bir vaattir; outcome, bu vaadin ne kadar tutulduğunu gösterir."
- "Rally Analyzer, 'oluşumun resmi' ile 'sonuç' arasındaki bağı öğrenmemizi sağlar."
- "Bu katman, snapshot'ların gelecekte nasıl performans gösterdiğini ölçer."
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from pathlib import Path
import sys

# Adjust path to allow imports if run directly or as module
from tezaver.snapshots.snapshot_engine import (
    get_symbol_pattern_dir,
    get_snapshot_file,
    load_features,
)

# --- Configuration ---
from tezaver.core.config import (
    RALLY_THRESHOLDS,
    LOOKAHEAD_BARS_MAP,
    DEFAULT_LOOKAHEAD_BARS,
)

def get_lookahead_bars(timeframe: str) -> int:
    """
    Returns the lookahead window size for a given timeframe.
    Lookahead defines how many bars into the future we check for a rally.
    """
    return LOOKAHEAD_BARS_MAP.get(timeframe, DEFAULT_LOOKAHEAD_BARS)



# --- Core Calculation ---

def _compute_outcomes_for_indices(
    close: pd.Series,
    indices: pd.Series,
    lookahead_bars: int
) -> Dict[str, pd.Series]:
    """
    Computes outcome metrics for specific indices in the close price series.
    
    Metrics:
    - future_max_gain_pct: Max percentage gain within lookahead window.
    - future_max_loss_pct: Max percentage loss (drawdown) within lookahead window.
    - hit_5p, hit_10p, hit_20p: Boolean flags for reaching thresholds.
    - rally_label: Classification string (none, rally_5p, rally_10p, rally_20p).
    
    Complexity: O(N * lookahead) - acceptable for offline analysis.
    """
    close_values = close.values
    n = len(close_values)
    
    future_max_gain_pct = []
    future_max_loss_pct = []
    hit_5p = []
    hit_10p = []
    hit_20p = []
    rally_labels = []
    
    for idx in indices:
        i = int(idx)
        
        # If index is invalid (NaN or out of bounds), handle gracefully
        if np.isnan(i) or i < 0 or i >= n:
            future_max_gain_pct.append(0.0)
            future_max_loss_pct.append(0.0)
            hit_5p.append(False)
            hit_10p.append(False)
            hit_20p.append(False)
            rally_labels.append("none")
            continue
            
        start = i + 1
        end = min(n, i + 1 + lookahead_bars)
        
        if start >= end:
            # Not enough future data
            future_max_gain_pct.append(0.0)
            future_max_loss_pct.append(0.0)
            hit_5p.append(False)
            hit_10p.append(False)
            hit_20p.append(False)
            rally_labels.append("none")
            continue
            
        window = close_values[start:end]
        price0 = close_values[i]
        
        if price0 == 0: # Avoid division by zero
             future_max_gain_pct.append(0.0)
             future_max_loss_pct.append(0.0)
             hit_5p.append(False)
             hit_10p.append(False)
             hit_20p.append(False)
             rally_labels.append("none")
             continue

        future_max = window.max()
        future_min = window.min()
        
        gain_pct = (future_max - price0) / price0
        loss_pct = (future_min - price0) / price0
        
        future_max_gain_pct.append(gain_pct)
        future_max_loss_pct.append(loss_pct)
        
        h5 = gain_pct >= 0.05
        h10 = gain_pct >= 0.10
        h20 = gain_pct >= 0.20
        
        hit_5p.append(h5)
        hit_10p.append(h10)
        hit_20p.append(h20)
        
        if h20:
            rally_labels.append("rally_20p")
        elif h10:
            rally_labels.append("rally_10p")
        elif h5:
            rally_labels.append("rally_5p")
        else:
            rally_labels.append("none")
            
    return {
        "future_max_gain_pct": pd.Series(future_max_gain_pct, index=indices.index),
        "future_max_loss_pct": pd.Series(future_max_loss_pct, index=indices.index),
        "hit_5p": pd.Series(hit_5p, dtype=bool, index=indices.index),
        "hit_10p": pd.Series(hit_10p, dtype=bool, index=indices.index),
        "hit_20p": pd.Series(hit_20p, dtype=bool, index=indices.index),
        "rally_label": pd.Series(rally_labels, dtype=str, index=indices.index),
    }


# --- Main Labeling Function ---

def label_snapshots_for_symbol_timeframe(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Labels snapshots with future outcome metrics.
    Saves to library/patterns/{SYMBOL}/snapshots_labeled_{TF}.parquet.
    
    This function measures the maximum rise/fall exhibited by the price after each snapshot
    and tags the snapshot with a rally degree. These tags will later be used to analyze
    'sincere' vs 'betraying' patterns.
    """
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

# ... (omitted unchanged lines)

def label_snapshots_for_symbol_timeframe(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Labels snapshots with future outcome metrics.
    Saves to library/patterns/{SYMBOL}/snapshots_labeled_{TF}.parquet.
    
    This function measures the maximum rise/fall exhibited by the price after each snapshot
    and tags the snapshot with a rally degree. These tags will later be used to analyze
    'sincere' vs 'betraying' patterns.
    """
    # 1. Load Features (Full History)
    try:
        df_features = load_features(symbol, timeframe)
    except FileNotFoundError as e:
        logger.error(f"Features not found for {symbol} {timeframe}: {e}")
        return pd.DataFrame()
        
    if df_features.empty:
        logger.warning(f"Features empty for {symbol} {timeframe}")
        return pd.DataFrame()
        
    # Ensure sorted by timestamp
    if "timestamp" in df_features.columns:
        df_features = df_features.sort_values("timestamp").reset_index(drop=True)
    
    # 2. Load Snapshots
    snapshot_file = get_snapshot_file(symbol, timeframe)
    if not snapshot_file.exists():
        logger.warning(f"Snapshots not found for {symbol} {timeframe}. Run M4 snapshot build first.")
        return pd.DataFrame()
        
    df_snap = pd.read_parquet(snapshot_file)
    if df_snap.empty:
        logger.warning(f"Snapshots empty for {symbol} {timeframe}")
        return df_snap
        
    # 3. Map Snapshots to Feature Indices
    # Create a map from timestamp to row index in features
    df_features["row_index"] = range(len(df_features))
    time_to_idx = dict(zip(df_features["timestamp"].tolist(), df_features["row_index"].tolist()))
    
    # Map snapshot timestamps to indices
    # Note: If a snapshot timestamp doesn't exist in features (unlikely if consistent), it becomes NaN
    df_snap["row_index"] = df_snap["timestamp"].map(time_to_idx)
    
    # 4. Compute Outcomes
    lookahead = get_lookahead_bars(timeframe)
    close_series = df_features["close"]
    
    # We pass the Series of indices from df_snap
    outcomes = _compute_outcomes_for_indices(close_series, df_snap["row_index"], lookahead)
    
    # 5. Add Outcome Columns
    df_snap["future_max_gain_pct"] = outcomes["future_max_gain_pct"]
    df_snap["future_max_loss_pct"] = outcomes["future_max_loss_pct"]
    df_snap["hit_5p"] = outcomes["hit_5p"].astype(int)
    df_snap["hit_10p"] = outcomes["hit_10p"].astype(int)
    df_snap["hit_20p"] = outcomes["hit_20p"].astype(int)
    df_snap["rally_label"] = outcomes["rally_label"]
    
    # Drop the temporary row_index column if desired, or keep it for debugging
    df_snap = df_snap.drop(columns=["row_index"])
    
    # 6. Save Labeled Snapshots
    symbol_dir = get_symbol_pattern_dir(symbol)
    labeled_file = symbol_dir / f"snapshots_labeled_{timeframe}.parquet"
    
    df_snap.to_parquet(labeled_file, index=False)
    
    return df_snap

def bulk_label_snapshots(symbols: List[str], timeframes: List[str]) -> None:
    """
    Labels snapshots for multiple coins and timeframes.
    """
    for symbol in symbols:
        for tf in timeframes:
            try:
                logger.info(f"Labelling snapshots for {symbol} {tf}...")
                label_snapshots_for_symbol_timeframe(symbol, tf)
            except Exception as e:
                logger.error(f"Failed to label snapshots for {symbol} {tf}: {e}", exc_info=True)
                continue
