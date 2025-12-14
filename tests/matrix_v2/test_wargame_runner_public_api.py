# War Game Runner Public API Smoke Test
"""
Smoke tests for War Game runner public API.
"""

import pytest

from tezaver.matrix.wargame.runner import run_silver_15m_from_patterns_for_symbol


class TestWargameRunnerPublicAPI:
    """Tests for War Game runner public API."""
    
    def test_run_silver_15m_btcusdt_smoke(self):
        """Basic smoke test for BTCUSDT with experiment mode."""
        report = run_silver_15m_from_patterns_for_symbol(
            symbol="BTCUSDT",
            risk_per_trade_pct=1.0,
            mode="experiment",
        )
        
        assert report.capital_start == 100.0
        assert report.capital_end >= 0.0
        assert report.trade_count >= 0
        assert hasattr(report, "equity_curve")
        assert hasattr(report, "events")
    
    def test_run_silver_15m_ethusdt_smoke(self):
        """Basic smoke test for ETHUSDT."""
        report = run_silver_15m_from_patterns_for_symbol(
            symbol="ETHUSDT",
            risk_per_trade_pct=1.0,
            mode="experiment",
        )
        
        assert report.capital_start == 100.0
        assert report.trade_count >= 0
    
    def test_run_silver_15m_contract_mode(self):
        """Test contract mode (may have 0 trades due to strict filters)."""
        report = run_silver_15m_from_patterns_for_symbol(
            symbol="BTCUSDT",
            risk_per_trade_pct=0.01,
            mode="contract",
        )
        
        # Contract mode may have 0 trades due to strict CoinPage V2 filters
        assert report.capital_start == 100.0
        assert report.capital_end >= 0.0
