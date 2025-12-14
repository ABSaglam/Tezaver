# Filter Debug Full Replay Tests
"""
Tests for full replay data source stats functions.
"""

import pytest
import pandas as pd

from tezaver.matrix.wargame.filter_debug import (
    SilverDataSourceStats,
    compute_silver_pattern_dataset_stats,
    compute_silver_full_replay_dataset_stats,
    format_data_source_stats_human,
)


class TestPatternDatasetStats:
    """Tests for pattern dataset stats."""
    
    def test_pattern_dataset_stats_basic(self):
        """Test basic pattern dataset stats for BTCUSDT."""
        stats = compute_silver_pattern_dataset_stats("BTCUSDT", "15m")
        
        assert stats.data_source == "pattern"
        assert stats.symbol == "BTCUSDT"
        assert stats.timeframe == "15m"
        
        # Should have data if dataset exists
        if stats.num_rows > 0:
            assert stats.num_labeled_events >= 0
    
    def test_pattern_dataset_stats_missing_symbol(self):
        """Test pattern dataset stats for non-existent symbol."""
        stats = compute_silver_pattern_dataset_stats("NONEXISTENT", "15m")
        
        assert stats.data_source == "pattern"
        assert stats.num_rows == 0
        assert stats.num_labeled_events == 0


class TestFullReplayDatasetStats:
    """Tests for full replay dataset stats."""
    
    def test_full_replay_dataset_stats_basic(self):
        """Test basic full replay dataset stats for BTCUSDT."""
        stats = compute_silver_full_replay_dataset_stats("BTCUSDT", "15m")
        
        assert stats.data_source == "full_replay"
        assert stats.symbol == "BTCUSDT"
        assert stats.timeframe == "15m"
        
        # Should have data if dataset exists
        if stats.num_rows > 0:
            assert stats.num_labeled_events >= 0
    
    def test_full_replay_dataset_stats_missing_symbol(self):
        """Test full replay dataset stats for non-existent symbol."""
        stats = compute_silver_full_replay_dataset_stats("NONEXISTENT", "15m")
        
        assert stats.data_source == "full_replay"
        assert stats.num_rows == 0
        assert stats.num_labeled_events == 0


class TestFormatDataSourceStats:
    """Tests for format_data_source_stats_human."""
    
    def test_format_with_data(self):
        """Test formatting with valid data."""
        stats = SilverDataSourceStats(
            data_source="pattern",
            symbol="BTCUSDT",
            timeframe="15m",
            start_ts=pd.Timestamp("2022-01-01"),
            end_ts=pd.Timestamp("2024-01-01"),
            num_rows=1000,
            num_labeled_events=50,
        )
        
        result = format_data_source_stats_human(stats)
        
        assert "📊 Pattern" in result
        assert "2022-01-01" in result
        assert "2024-01-01" in result
        assert "Satır:" in result
        assert "Label:" in result
    
    def test_format_with_no_data(self):
        """Test formatting with no data."""
        stats = SilverDataSourceStats(
            data_source="full_replay",
            symbol="BTCUSDT",
            timeframe="15m",
            start_ts=None,
            end_ts=None,
            num_rows=0,
            num_labeled_events=0,
        )
        
        result = format_data_source_stats_human(stats)
        
        assert "veri bulunamadı" in result
    
    def test_format_full_replay_label(self):
        """Test that full replay uses correct label."""
        stats = SilverDataSourceStats(
            data_source="full_replay",
            symbol="BTCUSDT",
            timeframe="15m",
            start_ts=pd.Timestamp("2022-01-01"),
            end_ts=pd.Timestamp("2024-01-01"),
            num_rows=70000,
            num_labeled_events=80,
        )
        
        result = format_data_source_stats_human(stats)
        
        assert "📈 Full Replay" in result
