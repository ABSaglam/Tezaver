"""
MX-24001: Test S3 BusAdapter put/get/list/exists

Uses botocore Stubber to mock S3 API calls.
"""

import json
import pytest
from io import BytesIO

try:
    import boto3
    from botocore.stub import Stubber
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

pytestmark = pytest.mark.skipif(not HAS_BOTO3, reason="boto3 not installed")


class TestS3BusPutGetListExists:
    """Test S3BusAdapter core operations with Stubber."""
    
    def test_put_json(self):
        """Test put_json calls S3 put_object."""
        from tezaver.platform.bus.adapter import S3BusAdapter
        
        adapter = S3BusAdapter(
            bucket="test-bucket",
            prefix="dev",
            endpoint_url="http://localhost:9000",
            access_key="test",
            secret_key="secret",
        )
        
        stubber = Stubber(adapter.client)
        
        # Expect put_object call
        stubber.add_response(
            "put_object",
            {},
            expected_params={
                "Bucket": "test-bucket",
                "Key": "dev/test/data.json",
                "Body": json.dumps({"key": "value"}, indent=2).encode("utf-8"),
                "ContentType": "application/json",
            }
        )
        
        with stubber:
            adapter.put_json("test/data.json", {"key": "value"})
            
        stubber.assert_no_pending_responses()
        
    def test_get_json(self):
        """Test get_json calls S3 get_object."""
        from tezaver.platform.bus.adapter import S3BusAdapter
        
        adapter = S3BusAdapter(
            bucket="test-bucket",
            prefix="dev",
            endpoint_url="http://localhost:9000",
            access_key="test",
            secret_key="secret",
        )
        
        stubber = Stubber(adapter.client)
        
        # Mock get_object response
        stubber.add_response(
            "get_object",
            {
                "Body": BytesIO(b'{"found": true}'),
            },
            expected_params={
                "Bucket": "test-bucket",
                "Key": "dev/test/data.json",
            }
        )
        
        with stubber:
            result = adapter.get_json("test/data.json")
            
        assert result == {"found": True}
        
    def test_exists_true(self):
        """Test exists returns True when object exists."""
        from tezaver.platform.bus.adapter import S3BusAdapter
        
        adapter = S3BusAdapter(
            bucket="test-bucket",
            prefix="",
            endpoint_url="http://localhost:9000",
            access_key="test",
            secret_key="secret",
        )
        
        stubber = Stubber(adapter.client)
        
        # Mock head_object success
        stubber.add_response(
            "head_object",
            {"ContentLength": 100},
            expected_params={
                "Bucket": "test-bucket",
                "Key": "test.json",
            }
        )
        
        with stubber:
            result = adapter.exists("test.json")
            
        assert result is True
        
    def test_bus_type(self):
        """Test S3BusAdapter has correct bus_type."""
        from tezaver.platform.bus.adapter import S3BusAdapter
        
        adapter = S3BusAdapter(
            bucket="test-bucket",
            prefix="dev",
            endpoint_url="http://localhost:9000",
            access_key="test",
            secret_key="secret",
        )
        
        assert adapter.bus_type == "s3"
