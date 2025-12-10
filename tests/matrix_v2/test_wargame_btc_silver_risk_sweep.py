# Test Risk Sweep Feature
"""
Tests for the Risk Sweep functionality in War Game.
"""

import pytest
from pathlib import Path


def test_risk_sweep_imports():
    """Test that risk sweep function can be imported."""
    from tezaver.matrix.wargame.runner import run_btc_silver_15m_risk_sweep
    assert callable(run_btc_silver_15m_risk_sweep)


def test_scenario_has_risk_parameter():
    """Test that WargameScenario has risk_per_trade_pct field."""
    from tezaver.matrix.wargame.scenarios import (
        WargameScenario,
        build_btc_silver_15m_patterns_scenario,
    )
    
    # Default should be 0.01 (1%)
    scenario = build_btc_silver_15m_patterns_scenario()
    assert hasattr(scenario, "risk_per_trade_pct")
    assert scenario.risk_per_trade_pct == 0.01
    
    # Should accept custom risk
    scenario_5pct = build_btc_silver_15m_patterns_scenario(risk_per_trade_pct=0.05)
    assert scenario_5pct.risk_per_trade_pct == 0.05
    
    scenario_full = build_btc_silver_15m_patterns_scenario(risk_per_trade_pct=1.0)
    assert scenario_full.risk_per_trade_pct == 1.0


def test_silver_strategist_accepts_risk():
    """Test that SilverStrategist accepts risk_per_trade_pct."""
    from tezaver.matrix.strategies.silver_core import (
        SilverStrategist,
        SilverStrategyConfig,
    )
    
    config = SilverStrategyConfig(symbol="BTCUSDT", timeframe="15m")
    
    # Default risk
    strategist_default = SilverStrategist(config)
    assert strategist_default._risk_pct == 1.0  # Default is 1%
    
    # Custom risk
    strategist_10pct = SilverStrategist(config, risk_per_trade_pct=10.0)
    assert strategist_10pct._risk_pct == 10.0


# Skip test if parquet file is missing
PARQUET_PATH = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")


@pytest.mark.skipif(
    not PARQUET_PATH.exists(),
    reason="rally_patterns_v1.parquet not found"
)
def test_risk_sweep_runs_for_multiple_profiles():
    """Test that risk sweep runs for multiple risk profiles."""
    from tezaver.matrix.wargame.runner import run_btc_silver_15m_risk_sweep
    
    results = run_btc_silver_15m_risk_sweep()
    
    # Should have at least 2 results
    assert len(results) >= 2
    
    # Check that expected risks are present
    risks = {r["risk_per_trade_pct"] for r in results}
    assert 0.01 in risks
    assert 0.10 in risks
    
    # Each result should have expected keys
    for result in results:
        assert "risk_per_trade_pct" in result
        assert "capital_start" in result
        assert "capital_end" in result
        assert "pnl_pct" in result
        assert "trade_count" in result
        assert "max_dd_pct" in result


@pytest.mark.skipif(
    not PARQUET_PATH.exists(),
    reason="rally_patterns_v1.parquet not found"
)
def test_risk_sweep_pnl_scales_with_risk():
    """Test that PnL scales approximately with risk percentage."""
    from tezaver.matrix.wargame.runner import run_btc_silver_15m_risk_sweep
    
    results = run_btc_silver_15m_risk_sweep()
    
    # Get results sorted by risk
    sorted_results = sorted(results, key=lambda x: x["risk_per_trade_pct"])
    
    # With higher risk, absolute PnL should scale (positive or negative)
    if len(sorted_results) >= 2:
        low_risk = sorted_results[0]
        high_risk = sorted_results[-1]
        
        # Higher risk should have higher absolute PnL change
        # (assuming trades are same direction)
        low_change = abs(low_risk["capital_end"] - low_risk["capital_start"])
        high_change = abs(high_risk["capital_end"] - high_risk["capital_start"])
        
        # High risk should result in larger absolute change
        # (unless all trades have 0 PnL)
        if low_change > 0:
            assert high_change >= low_change * 0.5  # Allow some variance
