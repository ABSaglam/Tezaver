# Silver Tightness V2 Tests
"""
Tests for tightness v2 semantic with dataset stats and interpolation.
"""

import pytest
from unittest.mock import MagicMock

from tezaver.matrix.strategies.silver_core import (
    SilverStrategyConfig,
    SilverDatasetStats,
    SilverFilterWindow,
    _interpolate_interval,
    build_silver_filter_window,
)


class TestInterpolateInterval:
    """Tests for _interpolate_interval helper."""
    
    def test_tightness_100_returns_card_range(self):
        """tightness=100 should return card range."""
        result = _interpolate_interval(
            global_min=0.0, global_max=100.0,
            card_min=20.0, card_max=30.0,
            tightness=100.0,
        )
        assert result == pytest.approx((20.0, 30.0))
    
    def test_tightness_0_returns_global_range(self):
        """tightness=0 should return global range."""
        result = _interpolate_interval(
            global_min=0.0, global_max=100.0,
            card_min=20.0, card_max=30.0,
            tightness=0.0,
        )
        assert result == pytest.approx((0.0, 100.0))
    
    def test_tightness_50_returns_midpoint(self):
        """tightness=50 should return midpoint."""
        result = _interpolate_interval(
            global_min=0.0, global_max=100.0,
            card_min=20.0, card_max=30.0,
            tightness=50.0,
        )
        # min: 0 * 0.5 + 20 * 0.5 = 10
        # max: 100 * 0.5 + 30 * 0.5 = 65
        assert result == pytest.approx((10.0, 65.0))


class TestBuildSilverFilterWindow:
    """Tests for build_silver_filter_window."""
    
    @pytest.fixture
    def sample_cfg(self):
        return SilverStrategyConfig(
            symbol="BTCUSDT",
            timeframe="15m",
            rsi_range=(20.0, 30.0),
            volume_rel_range=(2.0, 3.0),
            atr_pct_range=(0.5, 1.0),
            rsi_gap_1d_range=(-20.0, 0.0),
            rsi_1h_range=(20.0, 40.0),
        )
    
    @pytest.fixture
    def sample_stats(self):
        return SilverDatasetStats(
            rsi_15m_min=10.0,
            rsi_15m_max=60.0,
            volume_rel_15m_min=0.5,
            volume_rel_15m_max=6.0,
            atr_pct_15m_min=0.3,
            atr_pct_15m_max=2.0,
            rsi_gap_1d_min=-50.0,
            rsi_gap_1d_max=10.0,
            rsi_1h_min=10.0,
            rsi_1h_max=70.0,
        )
    
    def test_tightness_100_uses_card_range(self, sample_cfg, sample_stats):
        """tightness=100 should use card ranges exactly."""
        window = build_silver_filter_window(sample_cfg, sample_stats, tightness=100.0)
        
        assert window.rsi_15m_range == pytest.approx((20.0, 30.0))
        assert window.volume_rel_range == pytest.approx((2.0, 3.0))
        assert window.ml_enabled is True
    
    def test_tightness_0_uses_global_range_ml_disabled(self, sample_cfg, sample_stats):
        """tightness=0 should use global ranges and disable ML."""
        window = build_silver_filter_window(sample_cfg, sample_stats, tightness=0.0)
        
        assert window.rsi_15m_range == pytest.approx((10.0, 60.0))
        assert window.volume_rel_range == pytest.approx((0.5, 6.0))
        assert window.ml_enabled is False
        assert window.rsi_gap_1d_range is None
    
    def test_tightness_50_interpolates(self, sample_cfg, sample_stats):
        """tightness=50 should interpolate between card and global."""
        window = build_silver_filter_window(sample_cfg, sample_stats, tightness=50.0)
        
        # RSI: (10+20)/2=15, (60+30)/2=45
        assert window.rsi_15m_range == pytest.approx((15.0, 45.0))
        assert window.ml_enabled is True  # >= 40
    
    def test_tightness_30_disables_ml(self, sample_cfg, sample_stats):
        """tightness=30 (< 40) should disable ML filters."""
        window = build_silver_filter_window(sample_cfg, sample_stats, tightness=30.0)
        
        assert window.ml_enabled is False
        assert window.rsi_gap_1d_range is None
        assert window.rsi_1h_range is None
    
    def test_tightness_70_uses_card_ml_ranges(self, sample_cfg, sample_stats):
        """tightness=70 should use card ML ranges."""
        window = build_silver_filter_window(sample_cfg, sample_stats, tightness=70.0)
        
        assert window.ml_enabled is True
        assert window.rsi_gap_1d_range == pytest.approx((-20.0, 0.0))
        assert window.rsi_1h_range == pytest.approx((20.0, 40.0))
