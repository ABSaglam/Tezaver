"""
Tests for MultiTimeframeContext (MTC) v1
========================================

These tests verify that the MultiTimeframeContext schema enforcement and 
validation utilities work as expected.
"""

import pytest
import pandas as pd
import numpy as np
from typing import List

import sys
from pathlib import Path

# Fix pythonpath
sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

from tezaver.context.multitimeframe_context import (
    get_snapshot_column_names,
    get_required_mtc_columns,
    ensure_mtc_columns,
    validate_mtc_schema,
    EVENT_METADATA_COLUMNS,
    BASE_SNAPSHOT_FIELDS
)


def test_get_snapshot_column_names():
    """Verify snapshot column name generation."""
    cols = get_snapshot_column_names("15m")
    
    assert "rsi_15m" in cols
    assert "macd_phase_15m" in cols
    assert len(cols) == len(BASE_SNAPSHOT_FIELDS)
    
    # Check 1h
    cols_1h = get_snapshot_column_names("1h")
    assert "rsi_1h" in cols_1h


def test_get_required_mtc_columns():
    """Verify full schema column generation."""
    tfs = ["15m", "1h"]
    all_cols = get_required_mtc_columns(tfs)
    
    # Metadata presence
    for meta in EVENT_METADATA_COLUMNS:
        assert meta in all_cols
        
    # Snapshot columns presence
    for col in get_snapshot_column_names("15m"):
        assert col in all_cols
        
    for col in get_snapshot_column_names("1h"):
        assert col in all_cols
        
    # Should not have 4h columns
    assert "rsi_4h" not in all_cols


def test_ensure_mtc_columns_adds_missing_columns_with_nan():
    """
    Test that ensure_mtc_columns correctly adds missing columns
    and fills them with NaN.
    """
    # Create a minimal DataFrame with just some metadata
    df = pd.DataFrame([{
        "symbol": "BTCUSDT",
        "event_time": pd.Timestamp("2025-01-01"),
        "event_tf": "15m",
        "rally_bucket": "5p_10p"
    }])
    
    required_tfs = ["15m", "1h"]
    df_enriched = ensure_mtc_columns(df, required_tfs)
    
    # Check column existence
    assert "rsi_15m" in df_enriched.columns
    assert "trend_soul_1h" in df_enriched.columns
    
    # Check values are NaN for new columns
    assert pd.isna(df_enriched.iloc[0]["rsi_15m"])
    assert pd.isna(df_enriched.iloc[0]["trend_soul_1h"])
    
    # Check existing data is preserved
    assert df_enriched.iloc[0]["symbol"] == "BTCUSDT"


def test_validate_mtc_schema_raises_on_missing_required_columns():
    """Test that validation raises error when columns are missing."""
    df = pd.DataFrame([{"symbol": "BTC"}])
    required_tfs = ["1h"]
    
    with pytest.raises(ValueError, match="MTC Validation Failed"):
        validate_mtc_schema(df, required_tfs)


def test_fast15_output_structure_conformance():
    """
    Verify that a simulated Fast15 output conforms to the schema.
    This effectively tests the integration plan logic.
    """
    # Simulate a "raw" output from the scanner (before MTC enrichment)
    # Fast15 scanner produces these naturally
    raw_event = {
        "symbol": "ETHUSDT",
        "event_time": pd.Timestamp.now(),
        "rally_bucket": "10p_20p",
        "future_max_gain_pct": 0.12,
        "bars_to_peak": 8,
        # Some 15m data might exist
        "rsi_15m": 72.5,
        "volume_rel_15m": 2.1,
        # Missing others
    }
    
    df = pd.DataFrame([raw_event])
    
    # Simulate the logic added to fast15_rally_scanner.py
    df["event_tf"] = "15m"
    
    # Enforce schema
    required_tfs = ["15m", "1h", "4h", "1d"]
    df_final = ensure_mtc_columns(df, required_tfs)
    
    # Validate
    try:
        validate_mtc_schema(df_final, required_tfs)
    except ValueError as e:
        pytest.fail(f"Schema validation failed on simulated output: {e}")
        
    assert "rsi_15m" in df_final.columns
    assert "rsi_1h" in df_final.columns
    assert "rally_shape" in df_final.columns  # Added by schema even if missing in raw
    assert pd.isna(df_final.iloc[0]["rally_shape"])  # It should be NaN if not provided
