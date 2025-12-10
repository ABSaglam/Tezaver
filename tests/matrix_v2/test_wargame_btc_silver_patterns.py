# Matrix V2 Wargame BTC Silver Patterns Test
"""
Tests for War Game with real BTC 15m pattern data.
"""

import pytest
from pathlib import Path


def test_replay_datafeed_btc_silver_patterns_loads():
    """Test loading BTC 15m Silver patterns from parquet."""
    from tezaver.matrix.wargame.replay_datafeed import ReplayDataFeed
    
    parquet_path = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")
    
    if not parquet_path.exists():
        pytest.skip(f"Parquet file not found: {parquet_path}")
    
    feed = ReplayDataFeed.from_btc_15m_silver_patterns(parquet_path)
    
    assert feed.total_bars > 0
    assert feed._symbol == "BTCUSDT"
    assert feed._timeframe == "15m"
    
    # Check first bar has expected keys
    bar = feed.get_next_bar("BTCUSDT", "15m")
    assert bar is not None
    assert "rsi_15m" in bar
    assert "volume_rel" in bar
    assert "atr_pct" in bar
    assert "quality_score" in bar


def test_replay_datafeed_has_silver_labels():
    """Test that parquet data includes silver labels."""
    from tezaver.matrix.wargame.replay_datafeed import ReplayDataFeed
    
    parquet_path = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")
    
    if not parquet_path.exists():
        pytest.skip(f"Parquet file not found: {parquet_path}")
    
    feed = ReplayDataFeed.from_btc_15m_silver_patterns(parquet_path)
    
    bar = feed.get_next_bar("BTCUSDT", "15m")
    assert "label_is_silver" in bar
    assert "future_max_gain_pct" in bar


def test_run_btc_silver_15m_from_patterns_runs():
    """Test running War Game with real pattern data."""
    from tezaver.matrix.wargame.runner import run_btc_silver_15m_from_patterns
    
    parquet_path = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")
    
    if not parquet_path.exists():
        pytest.skip(f"Parquet file not found: {parquet_path}")
    
    report = run_btc_silver_15m_from_patterns(parquet_path)
    
    assert report.profile_id == "BTC_SILVER_15M_CORE_V1"
    assert report.scenario_id == "BTC_SILVER_15M_PATTERNS_V1"
    assert report.capital_start == 100.0
    assert isinstance(report.capital_end, float)
    assert report.capital_end >= 0


def test_build_btc_silver_15m_patterns_scenario():
    """Test building the patterns scenario."""
    from tezaver.matrix.wargame.scenarios import build_btc_silver_15m_patterns_scenario
    
    scenario = build_btc_silver_15m_patterns_scenario()
    
    assert scenario.profile_id == "BTC_SILVER_15M_CORE_V1"
    assert scenario.symbol == "BTCUSDT"
    assert scenario.timeframe == "15m"
    assert scenario.initial_capital == 100.0
