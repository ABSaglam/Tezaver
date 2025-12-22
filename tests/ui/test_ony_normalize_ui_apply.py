"""
Tests for ONY Normalize UI Apply Logic
=======================================

Tests the apply_normalize_to_annotation helper function.
"""

import pytest
import pandas as pd
from datetime import datetime
from tezaver.ui.ony_tab import apply_normalize_to_annotation
from tezaver.rally.normalize_engine import NormalizeResult
from tezaver.sniper.sniper_annotations import SniperAnnotation


class TestApplyNormalizeToAnnotation:
    """Test normalization application to annotations."""
    
    def test_apply_populates_all_fields(self):
        """Verify apply_normalize_to_annotation populates all normalized fields."""
        # Create annotation
        ann = SniperAnnotation(
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test_event_1",
            entry_bar_offset=5,
            note="Test annotation"
        )
        
        # Create normalize result
        norm_result = NormalizeResult(
            symbol="BTCUSDT",
            timeframe="15m",
            event_time_iso="2025-01-01T00:00:00",
            entry_offset_in=5,
            entry_offset_out=7,
            entry_ts_iso="2025-01-01T01:15:00",
            snap_reason="SNAP:pivot_high_window",
            snap_distance_bars=2,
            snap_confidence=0.70,
            snap_algo_version="normalize_entry_v1"
        )
        
        # Apply
        updated_ann = apply_normalize_to_annotation(ann, norm_result)
        
        # Verify all fields populated
        assert updated_ann.entry_bar_offset == 7
        assert updated_ann.normalized_entry_bar_offset == 7
        assert updated_ann.normalized_entry_ts == "2025-01-01T01:15:00"
        assert updated_ann.snap_reason == "SNAP:pivot_high_window"
        assert updated_ann.snap_distance_bars == 2
        assert updated_ann.snap_confidence == 0.70
        assert updated_ann.snap_algo_version == "normalize_entry_v1"
    
    def test_apply_updates_entry_offset(self):
        """Verify apply updates entry_bar_offset to snapped value."""
        ann = SniperAnnotation(
            symbol="ETHUSDT",
            timeframe="1h",
            event_id="test_event_2",
            entry_bar_offset=10,
        )
        
        norm_result = NormalizeResult(
            symbol="ETHUSDT",
            timeframe="1h",
            event_time_iso="2025-01-02T00:00:00",
            entry_offset_in=10,
            entry_offset_out=12,
            entry_ts_iso="2025-01-02T12:00:00",
            snap_reason="SNAP:pivot_high_window",
            snap_distance_bars=2,
            snap_confidence=0.70,
            snap_algo_version="normalize_entry_v1"
        )
        
        updated_ann = apply_normalize_to_annotation(ann, norm_result)
        
        # Verify entry_bar_offset updated from 10 to 12
        assert updated_ann.entry_bar_offset == 12
        assert updated_ann.normalized_entry_bar_offset == 12
    
    def test_apply_with_keep_reason(self):
        """Verify apply works with KEEP reason (no snap)."""
        ann = SniperAnnotation(
            symbol="SOLUSDT",
            timeframe="4h",
            event_id="test_event_3",
            entry_bar_offset=8,
        )
        
        norm_result = NormalizeResult(
            symbol="SOLUSDT",
            timeframe="4h",
            event_time_iso="2025-01-03T00:00:00",
            entry_offset_in=8,
            entry_offset_out=8,  # No change
            entry_ts_iso="2025-01-03T08:00:00",
            snap_reason="KEEP:base_is_pivot",
            snap_distance_bars=0,
            snap_confidence=0.55,
            snap_algo_version="normalize_entry_v1"
        )
        
        updated_ann = apply_normalize_to_annotation(ann, norm_result)
        
        # Verify KEEP case
        assert updated_ann.entry_bar_offset == 8  # No change
        assert updated_ann.snap_distance_bars == 0
        assert "KEEP" in updated_ann.snap_reason
        assert updated_ann.snap_confidence == 0.55
