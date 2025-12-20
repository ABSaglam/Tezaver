"""
MX-24002: Test Ops Unified Timeline
"""

import pytest
from tezaver.platform.bus.adapter import FsBusAdapter


def merge_all_events(bus, n: int) -> list:
    """Merge events from all streams, sorted by ts."""
    all_events = []
    
    for stream in ["mac", "matrix", "cloud"]:
        events = bus.tail_events(stream, n)
        for e in events:
            e["_stream"] = stream
        all_events.extend(events)
        
    all_events.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return all_events[:n]


class TestOpsUnifiedTimeline:
    """Test unified timeline merge and filter."""
    
    def test_merge_events_from_all_streams(self, tmp_path):
        """Test events from all streams are merged."""
        bus = FsBusAdapter(str(tmp_path))
        
        # Add events to each stream
        bus.append_event("mac", {"kind": "MAC_EVENT", "ts": 100})
        bus.append_event("matrix", {"kind": "MATRIX_EVENT", "ts": 200})
        bus.append_event("cloud", {"kind": "CLOUD_EVENT", "ts": 300})
        
        events = merge_all_events(bus, 10)
        
        assert len(events) == 3
        # Sorted by ts desc
        assert events[0]["kind"] == "CLOUD_EVENT"
        assert events[1]["kind"] == "MATRIX_EVENT"
        assert events[2]["kind"] == "MAC_EVENT"
        
    def test_merge_adds_stream_tag(self, tmp_path):
        """Test merged events have _stream tag."""
        bus = FsBusAdapter(str(tmp_path))
        
        bus.append_event("mac", {"kind": "A", "ts": 1})
        bus.append_event("cloud", {"kind": "B", "ts": 2})
        
        events = merge_all_events(bus, 10)
        
        assert events[0]["_stream"] == "cloud"
        assert events[1]["_stream"] == "mac"
        
    def test_filter_by_stream(self, tmp_path):
        """Test filtering by stream."""
        bus = FsBusAdapter(str(tmp_path))
        
        bus.append_event("mac", {"kind": "A", "ts": 1})
        bus.append_event("matrix", {"kind": "B", "ts": 2})
        bus.append_event("cloud", {"kind": "C", "ts": 3})
        
        events = merge_all_events(bus, 10)
        
        # Filter to matrix only
        filtered = [e for e in events if e.get("_stream") == "matrix"]
        
        assert len(filtered) == 1
        assert filtered[0]["kind"] == "B"
        
    def test_filter_by_kind(self, tmp_path):
        """Test filtering by kind substring."""
        bus = FsBusAdapter(str(tmp_path))
        
        bus.append_event("mac", {"kind": "JOB_START", "ts": 1})
        bus.append_event("mac", {"kind": "JOB_FAIL", "ts": 2})
        bus.append_event("mac", {"kind": "JOB_OK", "ts": 3})
        
        events = merge_all_events(bus, 10)
        
        # Filter to FAIL only
        filtered = [e for e in events if "FAIL" in e.get("kind", "")]
        
        assert len(filtered) == 1
        assert filtered[0]["kind"] == "JOB_FAIL"
        
    def test_merge_respects_n_limit(self, tmp_path):
        """Test merge respects n limit."""
        bus = FsBusAdapter(str(tmp_path))
        
        # Add many events
        for i in range(20):
            bus.append_event("mac", {"kind": f"E{i}", "ts": i})
            
        events = merge_all_events(bus, 5)
        
        assert len(events) == 5
