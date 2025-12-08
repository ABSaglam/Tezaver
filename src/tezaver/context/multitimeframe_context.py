"""
MultiTimeframeContext (MTC) v1
==============================

This module defines the standard data schema and utility functions for Tezaver's
"Time Labs" architecture. It ensures that rally scanners and other modules
produce dataframes with a consistent structure across different timeframes.

Core Responsibility:
- Define standard event metadata columns.
- Define standard snapshot column patterns per timeframe.
- Provide utilities to ensure schema compliance (add missing cols with NaN).
- Provide validation utilities.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Set
import pandas as pd
import numpy as np
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# SCHEMA DEFINITIONS
# ============================================================================

# Mandatory metadata columns for any MTC-compliant DataFrame
EVENT_METADATA_COLUMNS = [
    "symbol",
    "event_time",
    "event_tf",  # e.g., "15m", "1h", "4h", "1d", "1w"
    "rally_bucket",
    "future_max_gain_pct",
    "bars_to_peak",
    # Quality metrics (Rally v2)
    "rally_shape",
    "quality_score",
    "pre_peak_drawdown_pct",
    "trend_efficiency",
    "retention_3_pct",
    "retention_10_pct",
]

# Base names for snapshot features.
# These will be suffixed with _{tf} (e.g., rsi_15m)
BASE_SNAPSHOT_FIELDS = [
    "rsi",
    "rsi_ema",
    "macd_line",
    "macd_signal",
    "macd_hist",
    "macd_phase",
    "atr_pct",
    "volume_rel",
    "vol_spike",
    "vol_dry",
    "trend_soul",
    "regime",
    "risk_level",
]


# ============================================================================
# UTILITIES
# ============================================================================

def get_snapshot_column_names(tf: str) -> List[str]:
    """
    Generate standard snapshot column names for a specific timeframe.
    
    Args:
        tf: Timeframe string (e.g., "15m", "1h")
        
    Returns:
        List of column names like ['rsi_15m', 'macd_phase_1h', ...]
    """
    return [f"{field}_{tf}" for field in BASE_SNAPSHOT_FIELDS]


def get_required_mtc_columns(required_tfs: List[str]) -> List[str]:
    """
    Generate the full list of required columns for MTC v1 compliance.
    
    Args:
        required_tfs: List of timeframes to include (e.g. ["15m", "1h", "4h"])
        
    Returns:
        Combined list of event metadata columns + snapshot columns for each TF.
    """
    cols = list(EVENT_METADATA_COLUMNS)
    for tf in required_tfs:
        cols.extend(get_snapshot_column_names(tf))
    return cols


def ensure_mtc_columns(df: pd.DataFrame, required_tfs: List[str]) -> pd.DataFrame:
    """
    Ensure the DataFrame has all required MTC columns.
    Missing columns are added and filled with NaN.
    
    Args:
        df: Input DataFrame
        required_tfs: List of timeframes to enforce
        
    Returns:
        New DataFrame with guaranteed schema columns.
    """
    if df.empty:
        # If empty, just return an empty DF with correct columns
        cols = get_required_mtc_columns(required_tfs)
        return pd.DataFrame(columns=cols)
    
    df_out = df.copy()
    required_cols = get_required_mtc_columns(required_tfs)
    
    # Identify missing columns
    existing_cols = set(df_out.columns)
    missing_cols = [c for c in required_cols if c not in existing_cols]
    
    if missing_cols:
        logger.debug(f"MTC: Adding {len(missing_cols)} missing columns with NaN")
        # Add missing columns efficiently
        for col in missing_cols:
            df_out[col] = np.nan
            
    # Optional: Reorder columns for readability (Metadata first, then TFs)
    # Keeping extra columns that might be present is generally safe/good.
    # We just ensure the required ones exist.
    
    return df_out


def validate_mtc_schema(df: pd.DataFrame, required_tfs: List[str]) -> None:
    """
    Validate that the DataFrame strictly confirms to MTC schema requirements.
    
    Args:
        df: DataFrame to validate
        required_tfs: List of timeframes expected
        
    Raises:
        ValueError: If any required columns are missing.
    """
    if df.empty:
        return

    required_cols = get_required_mtc_columns(required_tfs)
    existing_cols = set(df.columns)
    missing = [c for c in required_cols if c not in existing_cols]
    
    if missing:
        msg = f"MTC Validation Failed: Missing {len(missing)} columns: {missing[:5]}..."
        logger.error(msg)
        raise ValueError(msg)
    
    logger.debug(f"MTC Schema Validated for {len(df)} rows.")
