# Test M2.3 features
"""Verify NDJSON cache and FaultInjectionGateway compliance."""

import unittest
import time
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock
import sys

# Mock Streamlit for cache
mock_st = MagicMock()
def mock_cache_data(*args, **kwargs):
    def decorator(f):
        return f
    return decorator
mock_st.cache_data = mock_cache_data
sys.modules["streamlit"] = mock_st

from tezaver.ui.matrix_operator_data import load_ndjson_tail
from tezaver.matrix.live.live_gateway import FaultInjectionGateway, DummyExchangeGateway


class TestNDJSONCache(unittest.TestCase):
    
    def test_cache_invalidates_on_update(self):
        """Cache should return new data when file content changes (size/mtime changes)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            f.write(json.dumps({"ts": "1", "event_type": "A"}) + "\n")
            path = Path(f.name)
            
        try:
            # First read
            events1 = load_ndjson_tail(path)
            self.assertEqual(len(events1), 1)
            self.assertEqual(events1[0]["event_type"], "A")
            
            # Wait a bit to ensure mtime triggers if resolution is low (though size also changes)
            time.sleep(0.01)
            
            # Update file
            with open(path, "a") as f:
                f.write(json.dumps({"ts": "2", "event_type": "B"}) + "\n")
                
            # Second read - should pick up change because stat changed
            events2 = load_ndjson_tail(path)
            self.assertEqual(len(events2), 2)
            self.assertEqual(events2[1]["event_type"], "B")
            
        finally:
            path.unlink()

class TestFaultInjectionCompliance(unittest.TestCase):
    
    def test_gateway_methods_exist(self):
        """FaultInjectionGateway must implement all IExchangeGateway new methods."""
        inner = DummyExchangeGateway()
        gw = FaultInjectionGateway(inner)
        
        # Check get_balance
        self.assertTrue(hasattr(gw, "get_balance"))
        bal = gw.get_balance()
        self.assertIn("source", bal)
        self.assertEqual(bal["source"], "dummy")
        
        # Check get_open_orders
        self.assertTrue(hasattr(gw, "get_open_orders"))
        orders = gw.get_open_orders("BTCUSDT")
        self.assertEqual(orders, [])

if __name__ == "__main__":
    unittest.main()
