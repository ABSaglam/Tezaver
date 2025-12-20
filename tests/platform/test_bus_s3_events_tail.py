"""
MX-24001: Test S3 BusAdapter events with Stubber

Tests append_event and tail_events with mocked S3.
"""

import json
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock

try:
    import boto3
    from botocore.stub import Stubber
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

pytestmark = pytest.mark.skipif(not HAS_BOTO3, reason="boto3 not installed")


class TestS3BusEventsTail:
    """Test S3BusAdapter event operations."""
    
    def test_append_event_key_format(self):
        """Test append_event creates correct key format."""
        from tezaver.platform.bus.adapter import S3BusAdapter
        
        adapter = S3BusAdapter(
            bucket="test-bucket",
            prefix="dev",
            endpoint_url="http://localhost:9000",
            access_key="test",
            secret_key="secret",
        )
        
        # Capture the key that was used
        captured_key = None
        
        def capture_put_object(**kwargs):
            nonlocal captured_key
            captured_key = kwargs.get("Key")
            return {}
        
        adapter.client.put_object = capture_put_object
        
        event_id = adapter.append_event("matrix", {"kind": "TEST"})
        
        # Key should contain: events/matrix/YYYY/MM/DD/HH/ts_uuid.json
        assert captured_key is not None
        assert "events/matrix/" in captured_key
        assert captured_key.endswith(".json")
        assert "_" in event_id  # ts_uuid format
        
    def test_tail_events_returns_events(self):
        """Test tail_events returns parsed events."""
        from tezaver.platform.bus.adapter import S3BusAdapter
        
        adapter = S3BusAdapter(
            bucket="test-bucket",
            prefix="dev",
            endpoint_url="http://localhost:9000",
            access_key="test",
            secret_key="secret",
        )
        
        # Mock list_objects_v2 to return 3 keys
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "dev/events/matrix/2024/01/01/00/1000_abc.json"},
                    {"Key": "dev/events/matrix/2024/01/01/00/2000_def.json"},
                    {"Key": "dev/events/matrix/2024/01/01/00/3000_ghi.json"},
                ]
            }
        ]
        adapter.client.get_paginator = MagicMock(return_value=mock_paginator)
        
        # Mock get_object to return event data
        def mock_get_object(**kwargs):
            key = kwargs.get("Key", "")
            if "1000" in key:
                return {"Body": BytesIO(b'{"kind": "A", "num": 1}')}
            elif "2000" in key:
                return {"Body": BytesIO(b'{"kind": "B", "num": 2}')}
            else:
                return {"Body": BytesIO(b'{"kind": "C", "num": 3}')}
                
        adapter.client.get_object = mock_get_object
        
        events = adapter.tail_events("matrix", n=2)
        
        # Should return 2 events, newest first (3000 then 2000)
        assert len(events) == 2
        assert events[0]["num"] == 3
        assert events[1]["num"] == 2
        
    def test_tail_events_empty(self):
        """Test tail_events returns empty list when no events."""
        from tezaver.platform.bus.adapter import S3BusAdapter
        
        adapter = S3BusAdapter(
            bucket="test-bucket",
            prefix="dev",
            endpoint_url="http://localhost:9000",
            access_key="test",
            secret_key="secret",
        )
        
        # Mock empty list
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Contents": []}]
        adapter.client.get_paginator = MagicMock(return_value=mock_paginator)
        
        events = adapter.tail_events("empty", n=10)
        
        assert events == []
