"""
MX-24001: Test FS BusAdapter tail_events
"""

import pytest
from tezaver.platform.bus.adapter import FsBusAdapter


class TestFsBusTailEvents:
    """Test FsBusAdapter append_event and tail_events."""
    
    def test_append_event_creates_file(self, tmp_path):
        """Test append_event creates events file."""
        bus = FsBusAdapter(str(tmp_path))
        
        event_id = bus.append_event("mac", {"kind": "TEST", "val": 1})
        
        assert event_id is not None
        assert (tmp_path / "events" / "mac.ndjson").exists()
        
    def test_append_multiple_events(self, tmp_path):
        """Test appending multiple events."""
        bus = FsBusAdapter(str(tmp_path))
        
        bus.append_event("matrix", {"kind": "A"})
        bus.append_event("matrix", {"kind": "B"})
        bus.append_event("matrix", {"kind": "C"})
        
        with open(tmp_path / "events" / "matrix.ndjson") as f:
            lines = f.readlines()
            
        assert len(lines) == 3
        
    def test_tail_events_returns_last_n(self, tmp_path):
        """Test tail_events returns last N events."""
        bus = FsBusAdapter(str(tmp_path))
        
        bus.append_event("cloud", {"kind": "E1", "num": 1})
        bus.append_event("cloud", {"kind": "E2", "num": 2})
        bus.append_event("cloud", {"kind": "E3", "num": 3})
        bus.append_event("cloud", {"kind": "E4", "num": 4})
        bus.append_event("cloud", {"kind": "E5", "num": 5})
        
        events = bus.tail_events("cloud", n=2)
        
        assert len(events) == 2
        assert events[0]["num"] == 5  # Newest first
        assert events[1]["num"] == 4
        
    def test_tail_events_empty_stream(self, tmp_path):
        """Test tail_events returns empty list for nonexistent stream."""
        bus = FsBusAdapter(str(tmp_path))
        
        events = bus.tail_events("nonexistent", n=10)
        
        assert events == []
        
    def test_tail_events_fewer_than_n(self, tmp_path):
        """Test tail_events returns all events if fewer than N."""
        bus = FsBusAdapter(str(tmp_path))
        
        bus.append_event("test", {"kind": "A"})
        bus.append_event("test", {"kind": "B"})
        
        events = bus.tail_events("test", n=10)
        
        assert len(events) == 2
