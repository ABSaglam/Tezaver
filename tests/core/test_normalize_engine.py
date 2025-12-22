"""
Tests for Normalize Engine v1
==============================

Tests offset-to-timestamp conversion and auto-snap functionality.
"""

import pytest
import pandas as pd
from datetime import datetime, timezone
from tezaver.rally.normalize_engine import (
    normalize_entry_from_df,
    find_event_bar_index,
    find_pivot_snap_offset,
    ensure_open_time,
)


class TestOffsetToTimestamp:
    """Test basic offset-to-timestamp conversion."""
    
    def test_offset_to_timestamp_basic(self):
        """Verify offset correctly maps to timestamp."""
        # Create fake history
        open_times = pd.date_range("2025-01-01 00:00", periods=10, freq="15min")
        df_history = pd.DataFrame({
            'open_time': open_times,
            'open': [100 + i for i in range(10)],
            'high': [105 + i for i in range(10)],
            'low': [95 + i for i in range(10)],
            'close': [102 + i for i in range(10)],
            'volume':  [1000 * (i+1) for i in range(10)]
        })
        
        # Event at index 3
        event_time = open_times[3]
        
        # Entry offset +2 (should map to index 5)
        entry_bar_offset = 2
        
        result = normalize_entry_from_df(
            df_history=df_history,
            symbol="TESTUSDT",
            timeframe="15m",
            event_time=event_time,
            entry_bar_offset=entry_bar_offset
        )
        
        # Base index would be 5apply
        # But highs are steadily increasing [105, 106, 107, 108, 109, 110, 111, 112, 113, 114]
        # Window around index 5 is [2:9] containing [107, 108, 109, 110, 111, 112, 113]
        # Highest is 113 at index 8
        # So it should snap to index 8 (offset +3 from base)
        
        expected_ts = open_times[8]  # Snapped to pivot high
        
        assert result.entry_offset_in == 2
        assert result.entry_offset_out == 5  # Event at 3, snap to index 8, offset = 8-3 = 5
        assert result.entry_ts_iso == expected_ts.isoformat()
        assert "SNAP" in result.snap_reason
        assert result.snap_algo_version == "normalize_entry_v1"


class TestPivotSnap:
    """Test pivot snap detection and offset adjustment."""
    
    def test_pivot_snap_changes_offset(self):
        """Verify snap adjusts offset when pivot is nearby."""
        # Create history with deliberate pivot at index 1
        open_times = pd.date_range("2025-01-01 00:00", periods=10, freq="15min")
        highs = [100, 110, 102, 103, 104, 105, 106, 107, 108, 109]  # Peak at index 1
        
        df_history = pd.DataFrame({
            'open_time': open_times,
            'open': [100] * 10,
            'high': highs,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000] * 10
        })
        
        # Event at index 0, entry offset 0 (base idx 0)
        event_time = open_times[0]
        entry_bar_offset = 0
        
        result = normalize_entry_from_df(
            df_history=df_history,
            symbol="TESTUSDT",
            timeframe="15m",
            event_time=event_time,
            entry_bar_offset=entry_bar_offset
        )
        
        # Should snap to index 1 (pivot high within ±3 window)
        assert result.entry_offset_out == 1, f"Expected snap to offset 1, got {result.entry_offset_out}"
        assert result.snap_distance_bars == 1
        assert "SNAP" in result.snap_reason
        assert result.snap_confidence >= 0.60


class TestClosedBarLock:
    """Test closed-bar lock ensures correct event bar selection."""
    
    def test_closed_bar_lock_selection(self):
        """Verify event_time selects last closed bar."""
        # Create history
        open_times = pd.date_range("2025-01-01 00:00", periods=10, freq="15min")
        df_history = pd.DataFrame({
            'open_time': open_times,
            'high': [100] * 10,
        })
        
        # Event time is 2 minutes after bar 3 opens
        event_time = open_times[3] + pd.Timedelta(minutes=2)
        
        # Find event bar index
        event_idx = find_event_bar_index(df_history, event_time)
        
        # Should select index 3 (last bar where open_time <= event_time)
        assert event_idx == 3, f"Expected index 3, got {event_idx}"
    
    def test_event_before_first_bar(self):
        """Verify behavior when event_time is before first bar."""
        open_times = pd.date_range("2025-01-01 00:00", periods=10, freq="15min")
        df_history = pd.DataFrame({'open_time': open_times})
        
        # Event before first bar
        event_time = open_times[0] - pd.Timedelta(minutes=30)
        
        event_idx = find_event_bar_index(df_history, event_time)
        
        # Should return 0 (defensive)
        assert event_idx == 0


class TestSnapMetadata:
    """Test snap metadata generation."""
    
    def test_snap_reason_keep_when_base_is_pivot(self):
        """Verify KEEP reason when base is already pivot."""
        # Create history where base is the highest
        open_times = pd.date_range("2025-01-01 00:00", periods=10, freq="15min")
        highs = [100, 102, 110, 103, 104, 105, 106, 107, 108, 109]  # Peak at index 2
        
        df_history = pd.DataFrame({
            'open_time': open_times,
            'high': highs,
        })
        
        # Base at index 2 (pivot)
        snap_delta, reason, confidence = find_pivot_snap_offset(df_history, base_idx=2, window_size=3)
        
        assert snap_delta == 0
        assert "KEEP:base_is_pivot" in reason
        assert confidence > 0.50
    
    def test_snap_confidence_scoring(self):
        """Verify confidence scores are reasonable."""
        # Distance 1 snap should have higher confidence
        open_times = pd.date_range("2025-01-01 00:00", periods=10, freq="15min")
        highs = [100, 110, 102, 103, 104, 105, 106, 107, 108, 109]
        
        df_history = pd.DataFrame({
            'open_time': open_times,
            'high': highs,
        })
        
        # Base at index 0, should snap to index 1 (distance 1)
        snap_delta, reason, confidence = find_pivot_snap_offset(df_history, base_idx=0, window_size=3)
        
        assert snap_delta == 1
        assert confidence >= 0.60, f"Expected confidence >= 0.60, got {confidence}"
