# Live vs War Game Parity Tests
"""
Tests for verifying parity between War Game and Live Cluster.
"""

import pytest
from pathlib import Path


def _has_silver_patterns(symbol: str) -> bool:
    """Check if pattern dataset exists for symbol."""
    path = Path(f"data/ai_datasets/{symbol}/15m/rally_patterns_v1.parquet")
    return path.exists()


class TestParitySilver15m:
    """Tests for Silver 15m Live vs War Game parity."""
    
    @pytest.mark.skipif(
        not _has_silver_patterns("BTCUSDT"),
        reason="BTCUSDT pattern dataset not available"
    )
    def test_silver_15m_live_vs_wargame_parity_btc(self):
        """BTC: Live and War Game should produce identical results."""
        from tezaver.matrix.wargame.parity_tools import run_silver_15m_live_vs_wargame_parity
        
        result = run_silver_15m_live_vs_wargame_parity(
            symbol="BTCUSDT",
            risk=1.0,
            mode="experiment",
        )
        
        # Results should match exactly (or within tiny tolerance)
        assert abs(result.diff_capital) < 1e-6, \
            f"Capital diff too large: {result.diff_capital}"
        assert abs(result.diff_pnl_pct) < 1e-6, \
            f"PnL% diff too large: {result.diff_pnl_pct}"
        assert result.is_parity
    
    @pytest.mark.skipif(
        not _has_silver_patterns("ETHUSDT"),
        reason="ETHUSDT pattern dataset not available"
    )
    def test_silver_15m_live_vs_wargame_parity_eth(self):
        """ETH: Live and War Game should produce identical results."""
        from tezaver.matrix.wargame.parity_tools import run_silver_15m_live_vs_wargame_parity
        
        result = run_silver_15m_live_vs_wargame_parity(
            symbol="ETHUSDT",
            risk=1.0,
            mode="experiment",
        )
        
        assert abs(result.diff_capital) < 1e-6
        assert abs(result.diff_pnl_pct) < 1e-6
    
    @pytest.mark.skipif(
        not _has_silver_patterns("SOLUSDT"),
        reason="SOLUSDT pattern dataset not available"
    )
    def test_silver_15m_live_vs_wargame_parity_sol(self):
        """SOL: Live and War Game should produce identical results."""
        from tezaver.matrix.wargame.parity_tools import run_silver_15m_live_vs_wargame_parity
        
        result = run_silver_15m_live_vs_wargame_parity(
            symbol="SOLUSDT",
            risk=1.0,
            mode="experiment",
        )
        
        assert abs(result.diff_capital) < 1e-6
        assert abs(result.diff_pnl_pct) < 1e-6
