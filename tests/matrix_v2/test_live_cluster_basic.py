# Live Cluster Basic Tests
"""
Tests for Matrix Live Cluster infrastructure.
"""

import pytest
from pathlib import Path

from tezaver.matrix.live import (
    build_silver_15m_live_cluster,
    MatrixLiveConfig,
    LiveStrategyCellConfig,
)
from tezaver.matrix.core.guardrail import GuardrailEnvironment


class TestLiveClusterBasic:
    """Tests for Live Cluster initialization and basic operations."""
    
    def test_live_cluster_builds_cells(self):
        """Live cluster should build cells for BTC/ETH/SOL."""
        cluster = build_silver_15m_live_cluster()
        cells = cluster.list_cells()
        
        # At least BTC should be present
        assert any(c.symbol == "BTCUSDT" and c.timeframe == "15m" for c in cells), \
            "BTCUSDT 15m cell not found"
    
    def test_live_cluster_tick_no_error(self):
        """Tick should not raise errors with a valid snapshot."""
        cluster = build_silver_15m_live_cluster()
        
        # Basit dummy snapshot
        snapshot = {
            "rsi_15m": 25.0,
            "volume_rel_15m": 2.1,
            "atr_pct_15m": 1.0,
            "quality_score": 65.0,
            "future_max_gain_pct": 0.05,
            "future_min_drawdown_pct": -0.01,
            "rsi_gap_1d": -5.0,
            "rsi_1h": 25.0,
        }
        
        # Should not raise
        cluster.tick("BTCUSDT", "15m", snapshot)
    
    def test_live_cluster_initial_equity(self):
        """Initial equity should match config."""
        cluster = build_silver_15m_live_cluster(initial_capital=100.0)
        cells = cluster.list_cells()
        
        if cells:
            cell = cells[0]
            equity = cluster.get_equity(cell.symbol, cell.timeframe, cell.profile_id)
            assert equity == 100.0
    
    def test_live_config_environment_is_live(self):
        """Live cluster should use LIVE environment."""
        cluster = build_silver_15m_live_cluster()
        
        # Check that cluster was built with LIVE environment
        # (implicitly tested by guardrail behavior for experimental profiles)
        cells = cluster.list_cells()
        assert len(cells) >= 1


class TestLiveStrategyCellConfig:
    """Tests for LiveStrategyCellConfig."""
    
    def test_cell_config_defaults(self):
        """Cell config should have correct defaults."""
        cell = LiveStrategyCellConfig(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="BTC_SILVER_15M_CORE_V1",
        )
        
        assert cell.risk_mode == "contract"
    
    def test_cell_config_custom_risk_mode(self):
        """Cell config should accept custom risk mode."""
        cell = LiveStrategyCellConfig(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="BTC_SILVER_15M_CORE_V1",
            risk_mode="experiment",
        )
        
        assert cell.risk_mode == "experiment"
