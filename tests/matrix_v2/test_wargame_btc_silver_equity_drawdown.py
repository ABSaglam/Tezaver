# Matrix V2 Wargame Equity & Drawdown Test
"""
Tests for equity curve tracking and max drawdown calculation.
"""

import pytest
from pathlib import Path


def test_wargame_report_has_equity_and_drawdown():
    """Test that WargameReport includes equity curve and drawdown."""
    from tezaver.matrix.wargame.runner import run_btc_silver_15m_from_patterns
    
    parquet_path = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")
    
    if not parquet_path.exists():
        pytest.skip(f"Parquet file not found: {parquet_path}")
    
    report = run_btc_silver_15m_from_patterns(parquet_path)
    
    assert report.capital_start == 100.0
    assert isinstance(report.equity_curve, list)
    assert len(report.equity_curve) >= 1
    # Drawdown should be <= 0 (negative or zero)
    assert report.max_drawdown_pct <= 0.0


def test_compute_max_drawdown_pct_basic():
    """Test max drawdown calculation with simple curves."""
    from tezaver.matrix.wargame.reports import compute_max_drawdown_pct
    
    # No drawdown - always going up
    curve_up = [100.0, 101.0, 102.0, 103.0]
    assert compute_max_drawdown_pct(curve_up) == 0.0
    
    # Simple drawdown
    curve_dd = [100.0, 110.0, 105.0, 108.0]  # Peak 110, drop to 105
    dd = compute_max_drawdown_pct(curve_dd)
    assert dd < 0
    assert abs(dd - (-0.0455)) < 0.01  # ~4.55% drawdown
    
    # Empty curve
    assert compute_max_drawdown_pct([]) == 0.0


def test_compute_max_drawdown_pct_multiple_drawdowns():
    """Test max drawdown with multiple drops."""
    from tezaver.matrix.wargame.reports import compute_max_drawdown_pct
    
    # Two drawdowns: first -5%, second -10%
    curve = [100.0, 105.0, 100.0, 110.0, 99.0, 115.0]
    dd = compute_max_drawdown_pct(curve)
    # Max DD should be from 110 to 99 = -10%
    assert abs(dd - (-0.10)) < 0.01


def test_wargame_account_store_equity_history():
    """Test that account store tracks equity history correctly."""
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    
    store = WargameAccountStore(initial_capital=100.0)
    
    # Initial history should have one entry
    history = store.get_equity_history()
    assert len(history) == 1
    assert history[0] == 100.0
    
    # Apply trades
    store.apply_execution({"event_type": "TRADE", "pnl": 5.0})
    store.apply_execution({"event_type": "TRADE", "pnl": -2.0})
    store.apply_execution({"event_type": "TRADE", "pnl": 3.0})
    
    history = store.get_equity_history()
    assert len(history) == 4  # Initial + 3 trades
    assert history == [100.0, 105.0, 103.0, 106.0]
    
    # Final equity
    assert store.get_equity() == 106.0


def test_wargame_account_store_reset_clears_history():
    """Test that reset clears equity history."""
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    
    store = WargameAccountStore(initial_capital=100.0)
    store.apply_execution({"event_type": "TRADE", "pnl": 10.0})
    store.reset()
    
    history = store.get_equity_history()
    assert len(history) == 1
    assert history[0] == 100.0
    assert store.get_equity() == 100.0
