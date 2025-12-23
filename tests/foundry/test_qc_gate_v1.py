"""
Tests for QC Gate v1
====================

Test the 7 QC rules and scoring system.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta

from tezaver.sniper.sniper_annotations import SniperAnnotation
from tezaver.foundry.qc_gate_v1 import evaluate
from tezaver.foundry.models import QCReport


class TestQCGateV1:
    """Test QC Gate evaluation logic."""
    
    def test_qc_pass_minimal(self):
        """Valid annotation with all required fields should PASS."""
        # Create fake history
        base_time = pd.Timestamp("2025-01-01 00:00:00")
        history_df = pd.DataFrame({
            'open_time': pd.date_range(base_time, periods=100, freq='15T'),
            'open': [100.0] * 100,
            'high': [101.0] * 100,
            'low': [99.0] * 100,
            'close': [100.5] * 100,
            'volume': [1000.0] * 100
        })
        
        # Create fake event
        event_row = pd.Series({
            'event_id': 'test_event_1',
            'event_time': base_time,
            'bars_to_peak': 20
        })
        
        # Create annotation
        ann = SniperAnnotation(
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test_event_1",
            entry_bar_offset=5,
            status="APPROVED"
        )
        
        # Set approved fields
        setattr(ann, 'approved_entry_bar_offset', 5)
        setattr(ann, 'approved_entry_ts', (base_time + timedelta(minutes=75)).isoformat())
        setattr(ann, 'approved_exit_bar_offset', 20)
        setattr(ann, 'snap_distance_entry', 2)
        setattr(ann, 'snap_confidence_entry', 0.75)
        
        # Run QC
        report = evaluate(ann, event_row, history_df)
        
        # Assertions
        assert report.qc_verdict == "PASS"
        assert report.score >= 60
        assert len(report.fails) == 0
    
    def test_qc_fail_missing_history(self):
        """Missing history should FAIL."""
        ann = SniperAnnotation(
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test_event_2",
            entry_bar_offset=5,
            status="APPROVED"
        )
        
        setattr(ann, 'approved_entry_bar_offset', 5)
        setattr(ann, 'approved_entry_ts', "2025-01-01T00:00:00")
        
        event_row = pd.Series({'event_id': 'test_event_2', 'event_time': pd.Timestamp("2025-01-01")})
        
        # Run QC with None history
        report = evaluate(ann, event_row, None)
        
        # Assertions
        assert report.qc_verdict == "FAIL"
        assert "HISTORY_MISSING" in report.fails
        assert report.score < 100
    
    def test_qc_fail_missing_approved_entry(self):
        """Missing approved entry should FAIL."""
        base_time = pd.Timestamp("2025-01-01 00:00:00")
        history_df = pd.DataFrame({
            'open_time': pd.date_range(base_time, periods=100, freq='15T'),
            'open': [100.0] * 100,
            'high': [101.0] * 100,
            'low': [99.0] * 100,
            'close': [100.5] * 100,
            'volume': [1000.0] * 100
        })
        
        ann = SniperAnnotation(
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test_event_3",
            entry_bar_offset=5,
            status="APPROVED"
        )
        
        # Don't set approved fields
        event_row = pd.Series({'event_id': 'test_event_3', 'event_time': base_time})
        
        report = evaluate(ann, event_row, history_df)
        
        assert report.qc_verdict == "FAIL"
        assert "APPROVED_ENTRY_MISSING" in report.fails
        assert "APPROVED_ENTRY_TS_INVALID" in report.fails
    
    def test_qc_warn_missing_exit(self):
        """Missing approved exit should WARN (not FAIL in v1)."""
        base_time = pd.Timestamp("2025-01-01 00:00:00")
        history_df = pd.DataFrame({
            'open_time': pd.date_range(base_time, periods=100, freq='15T'),
            'open': [100.0] * 100,
            'high': [101.0] * 100,
            'low': [99.0] * 100,
            'close': [100.5] * 100,
            'volume': [1000.0] * 100
        })
        
        ann = SniperAnnotation(
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test_event_4",
            entry_bar_offset=5,
            status="APPROVED"
        )
        
        setattr(ann, 'approved_entry_bar_offset', 5)
        setattr(ann, 'approved_entry_ts', (base_time + timedelta(minutes=75)).isoformat())
        # No approved_exit
        
        event_row = pd.Series({'event_id': 'test_event_4', 'event_time': base_time})
        
        report = evaluate(ann, event_row, history_df)
        
        assert "APPROVED_EXIT_MISSING" in report.warns
    
    def test_qc_fail_snap_distance(self):
        """Snap distance > 3 should FAIL."""
        base_time = pd.Timestamp("2025-01-01 00:00:00")
        history_df = pd.DataFrame({
            'open_time': pd.date_range(base_time, periods=100, freq='15T'),
            'open': [100.0] * 100,
            'high': [101.0] * 100,
            'low': [99.0] * 100,
            'close': [100.5] * 100,
            'volume': [1000.0] * 100
        })
        
        ann = SniperAnnotation(
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test_event_5",
            entry_bar_offset=5,
            status="APPROVED"
        )
        
        setattr(ann, 'approved_entry_bar_offset', 5)
        setattr(ann, 'approved_entry_ts', (base_time + timedelta(minutes=75)).isoformat())
        setattr(ann, 'snap_distance_entry', 5)  # >3, should fail
        
        event_row = pd.Series({'event_id': 'test_event_5', 'event_time': base_time})
        
        report = evaluate(ann, event_row, history_df)
        
        assert report.qc_verdict == "FAIL"
        assert "SNAP_DISTANCE_TOO_LARGE" in report.fails
    
    def test_qc_fail_time_inconsistency(self):
        """Entry before event should FAIL."""
        base_time = pd.Timestamp("2025-01-01 00:00:00")
        history_df = pd.DataFrame({
            'open_time': pd.date_range(base_time, periods=100, freq='15T'),
            'open': [100.0] * 100,
            'high': [101.0] * 100,
            'low': [99.0] * 100,
            'close': [100.5] * 100,
            'volume': [1000.0] * 100
        })
        
        ann = SniperAnnotation(
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test_event_6",
            entry_bar_offset=5,
            status="APPROVED"
        )
        
        setattr(ann, 'approved_entry_bar_offset', 5)
        setattr(ann, 'approved_entry_ts', (base_time - timedelta(minutes=15)).isoformat())  # Before event!
        
        event_row = pd.Series({'event_id': 'test_event_6', 'event_time': base_time})
        
        report = evaluate(ann, event_row, history_df)
        
        assert report.qc_verdict == "FAIL"
        assert "ENTRY_BEFORE_EVENT" in report.fails
    
    def test_scoring_system(self):
        """Verify score calculation."""
        base_time = pd.Timestamp("2025-01-01 00:00:00")
        history_df = pd.DataFrame({
            'open_time': pd.date_range(base_time, periods=100, freq='15T'),
            'open': [100.0] * 100,
            'high': [101.0] * 100,
            'low': [99.0] * 100,
            'close': [100.5] * 100,
            'volume': [1000.0] * 100
        })
        
        ann = SniperAnnotation(
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test_event_7",
            entry_bar_offset=5,
            status="APPROVED"
        )
        
        setattr(ann, 'approved_entry_bar_offset', 5)
        setattr(ann, 'approved_entry_ts', (base_time + timedelta(minutes=75)).isoformat())
        # Missing exit -> -10
        # Missing snap meta -> -10
        
        event_row = pd.Series({'event_id': 'test_event_7', 'event_time': base_time})
        
        report = evaluate(ann, event_row, history_df)
        
        # Score should be 100 - 10 (exit) - 10 (snap) = 80
        assert report.score == 80
        assert report.qc_verdict == "PASS"  # >= 60
