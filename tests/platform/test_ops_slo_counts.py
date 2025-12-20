"""
MX-24002: Test Ops SLO Counts
"""

import pytest
from tezaver.platform.bus.adapter import FsBusAdapter


def count_slo_events(events: list) -> dict:
    """Count SLO events by category."""
    return {
        "gaps": len([e for e in events if "GAP" in e.get("kind", "")]),
        "blocks": len([e for e in events if "BLOCK" in e.get("kind", "")]),
        "fails": len([e for e in events if "FAIL" in e.get("kind", "")]),
        "ticks": len([e for e in events if "TICK" in e.get("kind", "")]),
        "ok": len([e for e in events if "COMPLETED" in e.get("kind", "") or "JOB_OK" in e.get("kind", "")]),
    }


class TestOpsSLOCounts:
    """Test SLO event counting."""
    
    def test_count_gaps(self):
        """Test GAP event counting."""
        events = [
            {"kind": "GAP_DETECTED"},
            {"kind": "GAP_RESOLVED"},
            {"kind": "JOB_OK"},
        ]
        
        counts = count_slo_events(events)
        
        assert counts["gaps"] == 2
        
    def test_count_blocks(self):
        """Test BLOCK event counting."""
        events = [
            {"kind": "POSITION_BLOCKED"},
            {"kind": "BLOCK_ALERT"},
            {"kind": "JOB_OK"},
        ]
        
        counts = count_slo_events(events)
        
        assert counts["blocks"] == 2
        
    def test_count_fails(self):
        """Test FAIL event counting."""
        events = [
            {"kind": "JOB_FAIL"},
            {"kind": "CONNECTION_FAILED"},
            {"kind": "JOB_OK"},
        ]
        
        counts = count_slo_events(events)
        
        assert counts["fails"] == 2
        
    def test_count_ticks(self):
        """Test TICK event counting."""
        events = [
            {"kind": "RUNTIME_TICK"},
            {"kind": "RUNTIME_TICK"},
            {"kind": "RUNTIME_TICK"},
        ]
        
        counts = count_slo_events(events)
        
        assert counts["ticks"] == 3
        
    def test_count_ok(self):
        """Test OK/COMPLETED event counting."""
        events = [
            {"kind": "JOB_COMPLETED"},
            {"kind": "JOB_OK"},
            {"kind": "JOB_FAIL"},
        ]
        
        counts = count_slo_events(events)
        
        assert counts["ok"] == 2
        
    def test_count_mixed(self):
        """Test mixed event counting."""
        events = [
            {"kind": "GAP_DETECTED"},
            {"kind": "BLOCK_ALERT"},
            {"kind": "JOB_FAIL"},
            {"kind": "RUNTIME_TICK"},
            {"kind": "JOB_OK"},
        ]
        
        counts = count_slo_events(events)
        
        assert counts["gaps"] == 1
        assert counts["blocks"] == 1
        assert counts["fails"] == 1
        assert counts["ticks"] == 1
        assert counts["ok"] == 1
        
    def test_empty_events(self):
        """Test empty events list."""
        counts = count_slo_events([])
        
        assert counts["gaps"] == 0
        assert counts["blocks"] == 0
        assert counts["fails"] == 0
        assert counts["ticks"] == 0
        assert counts["ok"] == 0
