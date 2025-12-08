"""
Tests for Time-Labs v1 Scanner (1h & 4h)
========================================

Validates the detection logic, multi-timeframe enrichment, and summary generation.
"""

import pytest
import pandas as pd
import numpy as np
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Setup Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

from tezaver.rally.time_labs_scanner import (
    detect_rallies_for_timeframe,
    generate_time_labs_summary,
    enrich_event_with_multitf_snapshot_generic,
    run_1h_rally_scan_for_symbol
)


@pytest.fixture
def sample_features_df():
    """Create a sample 1h DataFrame with known price movement."""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="1h")
    df = pd.DataFrame({
        "timestamp": dates,
        "close": [100.0] * 100,
        "high": [100.0] * 100,
        # Some dummy indicators to test snapshot
        "rsi": [50.0] * 100,
        "macd_hist": [0.001] * 100
    })
    
    # Introduce a rally at index 50
    # Price jumps from 100 to 120 (20% gain) within next 5 bars
    df.loc[50, "close"] = 100.0
    df.loc[51:55, "high"] = [105, 110, 115, 120, 118]
    
    return df


def test_detect_rallies_for_timeframe_basic(sample_features_df):
    """Test standard rally detection logic."""
    events = detect_rallies_for_timeframe(
        df_tf=sample_features_df,
        timeframe="1h",
        min_gain_pct=0.05,  # 5%
        lookahead_bars=2,   # Reduced to avoid early detection
        buckets=[0.05, 0.10, 0.20],
        event_gap=2
    )
    
    assert not events.empty
    # With lookahead=2:
    # Index 49 sees 50 (100) and 51 (105). 105/100 = 5% gain. Triggers.
    # Index 50 sees 51 (105) and 52 (110). 110/100 = 10% gain. Triggers.
    # Index 51 sees 52 (110) and 53 (115). 115/105 = 9% gain. Triggers.
    # We expect something around 49-51.
    
    indices = events['event_index'].values
    assert any(49 <= x <= 51 for x in indices)
    
    # Check details of the first event found
    first_idx = indices[0]
    row = events[events['event_index'] == first_idx].iloc[0]
    assert row['future_max_gain_pct'] >= 0.05


def test_detect_rallies_for_timeframe_flat_no_events():
    """Test flat market yields no events."""
    dates = pd.date_range(start="2025-01-01", periods=50, freq="4h")
    df = pd.DataFrame({
        "timestamp": dates,
        "close": [100.0] * 50,
        "high": [100.0] * 50
    })
    
    events = detect_rallies_for_timeframe(
        df_tf=df,
        timeframe="4h",
        min_gain_pct=0.05,
        lookahead_bars=10,
        buckets=[0.05],
        event_gap=2
    )
    
    assert events.empty


def test_enrich_event_with_multitf_snapshot_generic():
    """Test generic multi-tf snapshot enrichment."""
    # Setup data
    t1 = pd.Timestamp("2025-01-01 12:00:00")
    
    # Base 1h data
    base_row = pd.Series({
        "close": 100.0,
        "atr": 5.0,
        "rsi": 60.0,
        "macd_hist": 0.002
    })
    
    # Context 4h data (one bar covering 12:00 or before)
    df_4h = pd.DataFrame({
        "timestamp": [pd.Timestamp("2025-01-01 12:00:00")], # Aligns exactly
        "close": 105.0,
        "rsi": 55.0,
        "macd_hist": -0.001
    })
    
    context_dfs = {"4h": df_4h}
    
    snapshot = enrich_event_with_multitf_snapshot_generic(
        event_time=t1,
        base_tf="1h",
        base_row=base_row,
        context_dfs=context_dfs
    )
    
    # Check base fields rename
    # rsi -> rsi_1h
    assert snapshot["rsi_1h"] == 60.0
    assert snapshot["atr_pct_1h"] == 5.0 # (5/100)*100
    
    # Check context fields rename
    # rsi -> rsi_4h from 4h DF
    assert snapshot["rsi_4h"] == 55.0
    
    # Check calculated fields
    assert "macd_phase_1h" in snapshot
    assert "macd_phase_4h" in snapshot


def test_generate_time_labs_summary():
    """Test JSON summary generator."""
    df_events = pd.DataFrame([
        {"rally_bucket": "5p_10p", "future_max_gain_pct": 0.08, "quality_score": 60, "rally_shape": "clean"},
        {"rally_bucket": "10p_20p", "future_max_gain_pct": 0.15, "quality_score": 80, "rally_shape": "spike"},
    ])
    
    summary = generate_time_labs_summary(
        df_events, 
        symbol="TEST",
        timeframe="1h",
        meta={}
    )
    
    assert summary["symbol"] == "TEST"
    assert summary["meta"]["total_events"] == 2
    assert "5p_10p" in summary["buckets"]
    assert "10p_20p" in summary["buckets"]
    
    # Check TR summary exists and contains count
    assert "toplam 2 rally" in summary["summary_tr"]


@patch("tezaver.rally.time_labs_scanner.load_features")
@patch("tezaver.rally.time_labs_scanner.enrich_rally_events_with_quality")
@patch("tezaver.rally.time_labs_scanner.validate_mtc_schema") 
def test_full_scan_integration_mocked(mock_validate, mock_enrich, mock_load, sample_features_df):
    """
    Test the full CLI entry point logic with mocked I/O.
    """
    # Mock Feature Loading
    def side_effect(symbol, tf):
        if tf == "1h": return sample_features_df
        return pd.DataFrame() # other TFs empty
        
    mock_load.side_effect = side_effect
    
    # Mock Enrichment (passthrough)
    def enrich_side_effect(events_df, **kwargs):
        # Just add dummy columns so MTC passes if we checked values, 
        # but mock_validate skips heavy checks logic inside test anyway
        events_df["quality_score"] = 50.0
        events_df["rally_shape"] = "unknown"
        # ... add minimal others if strictly required by underlying logic, 
        # but ensure_mtc_columns loads NaNs, so fine.
        return events_df
        
    mock_enrich.side_effect = enrich_side_effect
    
    # Run Function
    with patch("tezaver.core.coin_cell_paths.get_time_labs_rallies_path") as mock_path:
        mock_path.return_value = Path("/tmp/test.parquet")
        
        with patch("tezaver.core.coin_cell_paths.get_time_labs_rallies_summary_path") as mock_sum_path:
            mock_sum_path.return_value = Path("/tmp/test.json")
            
            # Need to mock to_parquet and open() writes to avoid FS errors
            with patch("pandas.DataFrame.to_parquet"), patch("builtins.open"):
                 result = run_1h_rally_scan_for_symbol("TESTUSDT")
                 
    # Verification
    assert result.symbol == "TESTUSDT"
    # We detected 1 event in unit test, should be same here
    assert result.num_events_total >= 1
    
    # Verify MTC Validation was called
    mock_validate.assert_called_once()
    
    # Verify Quality Enrichment was called
    mock_enrich.assert_called_once()
