# Test Multi-Coin Silver 15m Support
"""
Tests for multi-coin Silver 15m War Game support (BTC, ETH, SOL).
"""

import pytest
from pathlib import Path


def test_build_silver_15m_patterns_scenario_multi_coin():
    """Test that generic scenario builder works for multiple coins."""
    from tezaver.matrix.wargame.scenarios import build_silver_15m_patterns_scenario
    
    # BTC
    btc_scenario = build_silver_15m_patterns_scenario("BTCUSDT")
    assert btc_scenario.symbol == "BTCUSDT"
    assert btc_scenario.timeframe == "15m"
    assert btc_scenario.profile_id == "BTC_SILVER_15M_CORE_V1"
    assert btc_scenario.scenario_id == "BTC_SILVER_15M_PATTERNS_V1"
    
    # ETH
    eth_scenario = build_silver_15m_patterns_scenario("ETHUSDT")
    assert eth_scenario.symbol == "ETHUSDT"
    assert eth_scenario.profile_id == "ETH_SILVER_15M_CORE_V1"
    assert eth_scenario.scenario_id == "ETH_SILVER_15M_PATTERNS_V1"
    
    # SOL
    sol_scenario = build_silver_15m_patterns_scenario("SOLUSDT")
    assert sol_scenario.symbol == "SOLUSDT"
    assert sol_scenario.profile_id == "SOL_SILVER_15M_CORE_V1"
    
    # With custom risk
    high_risk = build_silver_15m_patterns_scenario("BTCUSDT", risk_per_trade_pct=0.10)
    assert high_risk.risk_per_trade_pct == 0.10


def test_replay_datafeed_generic_loader_signature():
    """Test that generic loader method exists with correct signature."""
    from tezaver.matrix.wargame.replay_datafeed import ReplayDataFeed
    
    assert hasattr(ReplayDataFeed, "from_symbol_timeframe_silver_patterns")
    # Check it's a classmethod
    assert callable(ReplayDataFeed.from_symbol_timeframe_silver_patterns)


def test_run_silver_15m_multi_coin_risk_sweep_import():
    """Test that multi-coin risk sweep function can be imported."""
    from tezaver.matrix.wargame.runner import (
        run_silver_15m_from_patterns_for_symbol,
        run_silver_15m_multi_coin_risk_sweep,
    )
    
    assert callable(run_silver_15m_from_patterns_for_symbol)
    assert callable(run_silver_15m_multi_coin_risk_sweep)


# Skip test if ETH/SOL datasets don't exist
BTC_PARQUET = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")


@pytest.mark.skipif(
    not BTC_PARQUET.exists(),
    reason="BTC rally_patterns_v1.parquet not found"
)
def test_run_silver_15m_from_patterns_for_symbol_btc():
    """Test generic runner works for BTC."""
    from tezaver.matrix.wargame.runner import run_silver_15m_from_patterns_for_symbol
    
    report = run_silver_15m_from_patterns_for_symbol("BTCUSDT", risk_per_trade_pct=0.01)
    
    assert report.capital_start == 100.0
    assert report.trade_count >= 0
    assert report.profile_id == "BTC_SILVER_15M_CORE_V1"


@pytest.mark.skipif(
    not BTC_PARQUET.exists(),
    reason="BTC rally_patterns_v1.parquet not found"
)
def test_run_silver_15m_multi_coin_risk_sweep_does_not_crash():
    """Test that multi-coin sweep runs without crashing."""
    from tezaver.matrix.wargame.runner import run_silver_15m_multi_coin_risk_sweep
    
    # This should not crash even if ETH/SOL datasets don't exist
    results = run_silver_15m_multi_coin_risk_sweep()
    
    # Should have at least BTC results (4 risk levels)
    btc_results = [r for r in results if r["symbol"] == "BTCUSDT"]
    assert len(btc_results) >= 1
    
    # Each result should have required fields
    for result in results:
        assert "symbol" in result
        assert "risk_per_trade_pct" in result
        assert "capital_start" in result
        assert "capital_end" in result
        assert "pnl_pct" in result
        assert "trade_count" in result
        assert "max_dd_pct" in result


def test_replay_datafeed_file_not_found_for_missing_symbol():
    """Test that FileNotFoundError is raised for missing datasets."""
    from tezaver.matrix.wargame.replay_datafeed import ReplayDataFeed
    
    with pytest.raises(FileNotFoundError):
        ReplayDataFeed.from_symbol_timeframe_silver_patterns(
            "NONEXISTENT_COIN",
            "15m"
        )
