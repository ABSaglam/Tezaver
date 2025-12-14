# Filter Settings and Relax Helper Tests
"""
Tests for Silver filter relaxation and debug tools.
"""

import pytest

from tezaver.matrix.strategies.silver_core import (
    SilverStrategyConfig,
    relax_silver_filters_for_experiment,
)
from tezaver.matrix.wargame.filter_debug import (
    analyze_silver_filter_squeeze,
    load_pattern_meta,
)


class TestRelaxSilverFilters:
    """Tests for relax_silver_filters_for_experiment."""
    
    def test_widen_factor_1_keeps_original(self):
        """widen_factor=1.0 should keep ranges unchanged."""
        cfg = SilverStrategyConfig(
            symbol="BTCUSDT",
            timeframe="15m",
            rsi_range=(20.0, 30.0),
            volume_rel_range=(2.0, 3.0),
            min_quality_score=60.0,
        )
        
        relaxed = relax_silver_filters_for_experiment(cfg, widen_factor=1.0)
        
        assert relaxed.rsi_range == (20.0, 30.0)
        assert relaxed.volume_rel_range == (2.0, 3.0)
        assert relaxed.min_quality_score == 60.0
    
    def test_widen_factor_2_doubles_range(self):
        """widen_factor=2.0 should double range width."""
        cfg = SilverStrategyConfig(
            symbol="BTCUSDT",
            timeframe="15m",
            rsi_range=(20.0, 30.0),  # width=10, center=25
            volume_rel_range=(2.0, 3.0),  # width=1, center=2.5
            min_quality_score=60.0,
        )
        
        relaxed = relax_silver_filters_for_experiment(cfg, widen_factor=2.0)
        
        # RSI: center=25, new_half=10, range=(15, 35)
        assert relaxed.rsi_range == pytest.approx((15.0, 35.0))
        # Volume: center=2.5, new_half=1, range=(1.5, 3.5)
        assert relaxed.volume_rel_range == pytest.approx((1.5, 3.5))
        # Quality: 60/2 = 30
        assert relaxed.min_quality_score == pytest.approx(30.0)
    
    def test_none_ranges_stay_none(self):
        """None ranges should stay None."""
        cfg = SilverStrategyConfig(
            symbol="BTCUSDT",
            timeframe="15m",
            rsi_range=None,
            volume_rel_range=None,
        )
        
        relaxed = relax_silver_filters_for_experiment(cfg, widen_factor=2.0)
        
        assert relaxed.rsi_range is None
        assert relaxed.volume_rel_range is None


class TestFilterDebug:
    """Tests for filter debug tools."""
    
    def test_analyze_filter_squeeze_returns_stats(self):
        """analyze_silver_filter_squeeze should return stage stats."""
        cfg = SilverStrategyConfig(
            symbol="BTCUSDT",
            timeframe="15m",
            # Very wide ranges to pass everything
            rsi_range=(0.0, 100.0),
            volume_rel_range=(0.0, 100.0),
            atr_pct_range=(0.0, 100.0),
        )
        
        stats = analyze_silver_filter_squeeze("BTCUSDT", "15m", cfg)
        
        # Should have some patterns if dataset exists
        if stats.total_patterns > 0:
            assert "1. RSI" in stats.stage_counts
            assert "2. + Volume" in stats.stage_counts
    
    def test_load_pattern_meta_returns_dict_or_none(self):
        """load_pattern_meta should return dict or None."""
        result = load_pattern_meta("BTCUSDT", "15m")
        
        if result is not None:
            assert "start_date" in result
            assert "end_date" in result
            assert "num_events" in result
            assert "years" in result
