# Hybrid War Game Basic Tests
"""
Tests for hybrid war game functionality.
"""

import pytest


class TestHybridRunner:
    """Tests for hybrid runner function."""
    
    def test_run_silver_15m_hybrid_for_symbol_basic(self):
        """Test basic hybrid run for BTCUSDT."""
        from tezaver.matrix.wargame.runner import run_silver_15m_hybrid_for_symbol
        
        try:
            result = run_silver_15m_hybrid_for_symbol(
                symbol="BTCUSDT",
                risk=0.01,
                mode="contract",
                tightness=50,
            )
        except FileNotFoundError:
            pytest.skip("Dataset not available")
        
        assert result.symbol == "BTCUSDT"
        assert result.timeframe == "15m"
        assert result.pattern_report is not None
        assert result.full_replay_report is not None
        
        # capital_start should be same for both
        assert result.pattern_report.capital_start == result.full_replay_report.capital_start
    
    def test_hybrid_delta_properties(self):
        """Test that delta properties are accessible and correct types."""
        from tezaver.matrix.wargame.runner import run_silver_15m_hybrid_for_symbol
        
        try:
            result = run_silver_15m_hybrid_for_symbol(
                symbol="BTCUSDT",
                risk=0.01,
                mode="contract",
                tightness=50,
            )
        except FileNotFoundError:
            pytest.skip("Dataset not available")
        
        # Properties should be accessible and correct types
        assert isinstance(result.delta_capital, float)
        assert isinstance(result.delta_pnl_pct, float)
        assert isinstance(result.delta_trades, int)
        assert isinstance(result.delta_max_dd_pct, float)


class TestHybridWargameResult:
    """Tests for HybridWargameResult dataclass."""
    
    def test_hybrid_result_structure(self):
        """Test HybridWargameResult can be constructed."""
        from tezaver.matrix.wargame.reports import HybridWargameResult, WargameReport
        
        pr = WargameReport(
            scenario_id="test_pattern",
            profile_id="TEST",
            capital_start=100.0,
            capital_end=110.0,
            trade_count=5,
            win_rate=0.6,
            max_drawdown_pct=-0.05,
        )
        
        fr = WargameReport(
            scenario_id="test_full",
            profile_id="TEST",
            capital_start=100.0,
            capital_end=105.0,
            trade_count=10,
            win_rate=0.5,
            max_drawdown_pct=-0.08,
        )
        
        result = HybridWargameResult(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="TEST",
            risk=0.01,
            mode="contract",
            tightness=50,
            pattern_report=pr,
            full_replay_report=fr,
        )
        
        assert result.symbol == "BTCUSDT"
        assert result.delta_capital == -5.0  # 105 - 110
        assert result.delta_trades == 5  # 10 - 5
