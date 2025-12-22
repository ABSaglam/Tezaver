"""
Tests for ONY v1.2 Approve Workflow
====================================

Tests the approve workflow with manual/suggested/approved separation.
"""

import pytest
import pandas as pd
from datetime import datetime
from tezaver.ui.ony_tab import approve_suggested
from tezaver.sniper.sniper_annotations import SniperAnnotation


class TestApproveWorkflow:
    """Test ONY v1.2 approve workflow."""
    
    def test_approve_use_suggested(self):
        """Verify approve_use_suggested sets approved fields and status."""
        # Create annotation with manual values
        ann = SniperAnnotation(
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test_event_1",
            entry_bar_offset=5,
            manual_entry_bar_offset=5,
            manual_exit_bar_offset=10,
        )
        
        # Create preview
        preview = {
            "suggested_entry": 7,
            "suggested_exit": 12,
            "snap_reason_entry": "SNAP:pivot_high_window",
            "snap_distance_entry": 2,
            "snap_confidence_entry": 0.70,
            "snap_algo_version_entry": "normalize_entry_v1",
            "snap_reason_exit": "SNAP:pivot_high_window",
            "snap_distance_exit": 2,
            "snap_confidence_exit": 0.70,
            "snap_algo_version_exit": "normalize_entry_v1",
        }
        
        # Mock event_time (approval may try to load history)
        event_time = pd.Timestamp("2025-01-01 00:00:00")
        
        # Approve (will fail on history load but should set offsets)
        updated_ann = approve_suggested(ann, preview, "BTCUSDT", "15m", event_time)
        
        # Verify approved offsets set
        assert updated_ann.approved_entry_bar_offset == 7
        assert updated_ann.approved_exit_bar_offset == 12
        
        # Verify status changed to APPROVED
        assert updated_ann.status == "APPROVED"
        
        # Verify snap metadata copied
        assert updated_ann.snap_reason_entry == "SNAP:pivot_high_window"
        assert updated_ann.snap_confidence_entry == 0.70
    
    def test_manual_preserved_on_approve(self):
        """Verify manual values are preserved after approval."""
        ann = SniperAnnotation(
            symbol="ETHUSDT",
            timeframe="1h",
            event_id="test_event_2",
            entry_bar_offset=8,
            manual_entry_bar_offset=8,
        )
        
        preview = {
            "suggested_entry": 9,
            "snap_reason_entry": "SNAP:pivot",
            "snap_distance_entry": 1,
            "snap_confidence_entry": 0.65,
            "snap_algo_version_entry": "normalize_v1",
        }
        
        event_time = pd.Timestamp("2025-01-02 00:00:00")
        updated_ann = approve_suggested(ann, preview, "ETHUSDT", "1h", event_time)
        
        # Manual should be preserved
        assert updated_ann.manual_entry_bar_offset == 8
        
        # Approved should be updated
        assert updated_ann.approved_entry_bar_offset == 9
    
    def test_approve_sets_status_approved(self):
        """Verify approve workflow sets status to APPROVED."""
        ann = SniperAnnotation(
            symbol="SOLUSDT",
            timeframe="4h",
            event_id="test_event_3",
            entry_bar_offset=3,
            status="PENDING",
        )
        
        preview = {
            "suggested_entry": 4,
            "snap_reason_entry": "KEEP:base_is_pivot",
            "snap_distance_entry": 0,
            "snap_confidence_entry": 0.55,
            "snap_algo_version_entry": "normalize_v1",
        }
        
        event_time = pd.Timestamp("2025-01-03 00:00:00")
        updated_ann = approve_suggested(ann, preview, "SOLUSDT", "4h", event_time)
        
        # Status should change from PENDING to APPROVED
        assert updated_ann.status == "APPROVED"
