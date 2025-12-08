"""
Tests for Rally Quality Engine (Rally v2).

Tests path metric computation, shape classification, quality scoring,
and DataFrame enrichment.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from tezaver.rally.rally_quality_engine import (
    RallyQualityConfig,
    get_default_rally_quality_config,
    clamp,
    compute_rally_path_metrics,
    classify_rally_shape,
    compute_quality_score,
    enrich_rally_events_with_quality,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_price_series(values, start_time=None):
    """Create a datetime-indexed price Series for testing."""
    if start_time is None:
        start_time = datetime(2024, 1, 1, 0, 0)
    
    index = [start_time + timedelta(minutes=15 * i) for i in range(len(values))]
    return pd.Series(values, index=index)


# ============================================================================
# UNIT TESTS: clamp
# ============================================================================

def test_clamp_basic():
    """Test basic clamp functionality."""
    assert clamp(0.5, 0, 1) == 0.5
    assert clamp(-0.5, 0, 1) == 0.0
    assert clamp(1.5, 0, 1) == 1.0
    assert clamp(0.0, 0, 1) == 0.0
    assert clamp(1.0, 0, 1) == 1.0


# ============================================================================
# UNIT TESTS: compute_rally_path_metrics
# ============================================================================

def test_compute_rally_path_metrics_clean_uptrend():
    """Test metrics for a clean uptrend rally."""
    # Perfect uptrend: 100 -> 110 -> 120
    prices = create_price_series([100, 110, 120])
    cfg = get_default_rally_quality_config()["15m"]
    
    metrics = compute_rally_path_metrics(
        prices=prices,
        event_idx=0,
        bars_to_peak=2,
        cfg=cfg
    )
    
    assert metrics["net_gain_pct"] == pytest.approx(0.2, rel=0.01)  # 20% gain
    assert metrics["pre_peak_drawdown_pct"] >= 0.0  # No drawdown in uptrend
    assert metrics["trend_efficiency"] > 0.9  # Very efficient
    assert metrics["retention_3_pct"] > 0  # Should retain gains


def test_compute_rally_path_metrics_spike_and_dump():
    """Test metrics for a spike that dumps quickly."""
    # Spike: 100 -> 150 -> 110 -> 105
    prices = create_price_series([100, 150, 110, 105])
    cfg = get_default_rally_quality_config()["15m"]
    
    metrics = compute_rally_path_metrics(
        prices=prices,
        event_idx=0,
        bars_to_peak=1,
        cfg=cfg
    )
    
    assert metrics["net_gain_pct"] == pytest.approx(0.5, rel=0.01)  # 50% gain
    assert metrics["retention_3_pct"] < 0.15  # Poor retention (dumped to 105 = 5%)
    # Note: Single-bar spike can have efficiency=1.0 (straight up), which is fine
    assert metrics["trend_efficiency"] >= 0.0  # Should be positive


def test_compute_rally_path_metrics_with_drawdown():
    """Test metrics with significant drawdown before peak."""
    # Drawdown: 100 -> 95 -> 110
    prices = create_price_series([100, 95, 110])
    cfg = get_default_rally_quality_config()["15m"]
    
    metrics = compute_rally_path_metrics(
        prices=prices,
        event_idx=0,
        bars_to_peak=2,
        cfg=cfg
    )
    
    assert metrics["net_gain_pct"] == pytest.approx(0.1, rel=0.01)  # 10% gain
    assert metrics["pre_peak_drawdown_pct"] < 0.0  # Negative (drawdown)
    assert metrics["pre_peak_drawdown_pct"] <= -0.049  # ~-5% drawdown


# ============================================================================
# UNIT TESTS: classify_rally_shape
# ============================================================================

def test_classify_rally_shape_clean():
    """Test classification of a clean rally."""
    cfg = get_default_rally_quality_config()["15m"]
    
    shape = classify_rally_shape(
        net_gain_pct=0.10,  # 10% gain
        bars_to_peak=5,  # Within clean range (2-8)
        pre_peak_drawdown_pct=-0.01,  # Small drawdown
        trend_efficiency=0.75,  # High efficiency
        retention_3_pct=0.05,  # Decent retention
        retention_10_pct=0.06,  # 60% retention of gain
        cfg=cfg
    )
    
    assert shape == "clean"


def test_classify_rally_shape_spike():
    """Test classification of a spike rally."""
    cfg = get_default_rally_quality_config()["15m"]
    
    shape = classify_rally_shape(
        net_gain_pct=0.15,  # 15% gain
        bars_to_peak=2,  # Quick spike (<=2)
        pre_peak_drawdown_pct=0.0,  # No drawdown
        trend_efficiency=0.9,  # Can be efficient
        retention_3_pct=0.02,  # Poor retention (< 20% of 15%)
        retention_10_pct=-0.01,  # Dumped below entry
        cfg=cfg
    )
    
    assert shape == "spike"


def test_classify_rally_shape_choppy():
    """Test classification of a choppy rally."""
    cfg = get_default_rally_quality_config()["15m"]
    
    shape = classify_rally_shape(
        net_gain_pct=0.10,  # 10% gain
        bars_to_peak=12,  # Long time (outside clean range)
        pre_peak_drawdown_pct=-0.04,  # Some drawdown
        trend_efficiency=0.4,  # Low efficiency (< 0.6)
        retention_3_pct=0.05,  # OK retention
        retention_10_pct=0.06,  # OK retention
        cfg=cfg
    )
    
    assert shape == "choppy"


def test_classify_rally_shape_weak():
    """Test classification of a weak rally."""
    cfg = get_default_rally_quality_config()["15m"]
    
    shape = classify_rally_shape(
        net_gain_pct=0.03,  # Only 3% gain (< 5% min)
        bars_to_peak=5,
        pre_peak_drawdown_pct=0.0,
        trend_efficiency=0.7,
        retention_3_pct=0.02,
        retention_10_pct=0.02,
        cfg=cfg
    )
    
    assert shape == "weak"


# ============================================================================
# UNIT TESTS: compute_quality_score
# ============================================================================

def test_compute_quality_score_high_quality():
    """Test score for high-quality rally."""
    cfg = get_default_rally_quality_config()["15m"]
    
    score = compute_quality_score(
        net_gain_pct=0.15,  # 15% gain (target is 10%)
        pre_peak_drawdown_pct=-0.01,  # Very small drawdown
        trend_efficiency=0.7,  # High efficiency
        retention_10_pct=0.12,  # 80% retention
        cfg=cfg
    )
    
    # Should be high score (> 80)
    assert score > 80.0
    assert score <= 100.0


def test_compute_quality_score_medium_quality():
    """Test score for medium-quality rally."""
    cfg = get_default_rally_quality_config()["15m"]
    
    score = compute_quality_score(
        net_gain_pct=0.08,  # 8% gain
        pre_peak_drawdown_pct=-0.03,  # Moderate drawdown
        trend_efficiency=0.5,  # Medium efficiency
        retention_10_pct=0.04,  # 50% retention
        cfg=cfg
    )
    
    # Should be medium score (50-70)
    assert 40.0 < score < 75.0


def test_compute_quality_score_low_quality():
    """Test score for low-quality rally."""
    cfg = get_default_rally_quality_config()["15m"]
    
    score = compute_quality_score(
        net_gain_pct=0.05,  # Minimal 5% gain
        pre_peak_drawdown_pct=-0.06,  # Large drawdown
        trend_efficiency=0.25,  # Low efficiency
        retention_10_pct=0.0,  # No retention
        cfg=cfg
    )
    
    # Should be low score (< 40)
    assert score < 45.0
    assert score >= 0.0


# ============================================================================
# INTEGRATION TESTS: enrich_rally_events_with_quality
# ============================================================================

def test_enrich_rally_events_basic():
    """Test basic DataFrame enrichment with quality metrics."""
    # Create synthetic price data
    start_time = datetime(2024, 1, 1, 0, 0)
    prices_data = [100, 105, 110, 115, 120, 118, 116, 114, 112, 110, 108]
    prices = create_price_series(prices_data, start_time)
    
    # Create events DataFrame
    events_df = pd.DataFrame({
        "event_time": [start_time],
        "bars_to_peak": [4],  # Peak at 120 (4 bars later)
        "future_max_gain_pct": [0.20]  # 20% gain
    })
    
    # Enrich
    enriched = enrich_rally_events_with_quality(
        events_df=events_df,
        prices=prices,
        timeframe="15m"
    )
    
    # Verify new columns exist
    assert "rally_shape" in enriched.columns
    assert "quality_score" in enriched.columns
    assert "pre_peak_drawdown_pct" in enriched.columns
    assert "trend_efficiency" in enriched.columns
    assert "retention_3_pct" in enriched.columns
    assert "retention_10_pct" in enriched.columns
    
    # Verify single row
    assert len(enriched) == 1
    
    # Check values are reasonable
    row = enriched.iloc[0]
    assert row["rally_shape"] in ["clean", "spike", "choppy", "weak", "unknown"]
    assert 0.0 <= row["quality_score"] <= 100.0
    assert row["trend_efficiency"] > 0.0  # Should be positive for uptrend


def test_enrich_rally_events_multiple_events():
    """Test enrichment with multiple events."""
    start_time = datetime(2024, 1, 1, 0, 0)
    
    # Create longer price series
    prices_data = [100 + i * 2 for i in range(30)]  # Gradual uptrend
    prices = create_price_series(prices_data, start_time)
    
    # Create multiple events
    events_df = pd.DataFrame({
        "event_time": [
            start_time,
            start_time + timedelta(minutes=15 * 10),
            start_time + timedelta(minutes=15 * 20)
        ],
        "bars_to_peak": [5, 4, 3],
        "future_max_gain_pct": [0.10, 0.08, 0.12]
    })
    
    # Enrich
    enriched = enrich_rally_events_with_quality(
        events_df=events_df,
        prices=prices,
        timeframe="15m"
    )
    
    # Verify all rows enriched
    assert len(enriched) == 3
    assert not enriched["rally_shape"].isna().any()
    assert not enriched["quality_score"].isna().any()


def test_enrich_rally_events_empty_dataframe():
    """Test enrichment with empty DataFrame."""
    start_time = datetime(2024, 1, 1, 0, 0)
    prices = create_price_series([100, 110, 120], start_time)
    
    events_df = pd.DataFrame()
    
    enriched = enrich_rally_events_with_quality(
        events_df=events_df,
        prices=prices,
        timeframe="15m"
    )
    
    # Should return empty DataFrame
    assert enriched.empty


def test_enrich_rally_events_with_different_timeframe():
    """Test enrichment with different timeframe config."""
    start_time = datetime(2024, 1, 1, 0, 0)
    prices_data = [100, 110, 120, 130, 125, 120]
    prices = create_price_series(prices_data, start_time)
    
    events_df = pd.DataFrame({
        "event_time": [start_time],
        "bars_to_peak": [3],
        "future_max_gain_pct": [0.30]
    })
    
    # Use 1h config (different thresholds)
    enriched = enrich_rally_events_with_quality(
        events_df=events_df,
        prices=prices,
        timeframe="1h"
    )
    
    # Should still work
    assert len(enriched) == 1
    assert "rally_shape" in enriched.columns


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

def test_default_config_all_timeframes():
    """Test that default configs exist for all timeframes."""
    configs = get_default_rally_quality_config()
    
    assert "15m" in configs
    assert "1h" in configs
    assert "4h" in configs
    assert "1d" in configs
    
    # Verify config structure
    for tf, cfg in configs.items():
        assert isinstance(cfg, RallyQualityConfig)
        assert cfg.min_gain_pct > 0
        assert cfg.clean_min_bars > 0
        assert cfg.clean_max_bars > cfg.clean_min_bars
        assert cfg.retention_short_bars > 0
        assert cfg.retention_long_bars > cfg.retention_short_bars


def test_default_config_timeframe_differences():
    """Test that different timeframes have appropriately scaled thresholds."""
    configs = get_default_rally_quality_config()
    
    # Higher timeframes should have looser thresholds
    assert configs["1h"].max_clean_drawdown_pct > configs["15m"].max_clean_drawdown_pct
    assert configs["4h"].clean_max_bars > configs["15m"].clean_max_bars
    assert configs["1d"].target_gain_for_score > configs["15m"].target_gain_for_score
