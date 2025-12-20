# Test Internal Account State
"""Unit tests for deriving internal component state from telemetry."""

import unittest
import json
import tempfile
from pathlib import Path
from tezaver.matrix.live.account_state import get_internal_positions_from_events

class TestAccountState(unittest.TestCase):
    """Tests for account_state module."""
    
    def test_parse_open_close_events(self):
        """Test parsing PROOF_OPEN and PROOF_CLOSE events."""
        events = [
            {"event_type": "PROOF_OPEN", "symbol": "BTCUSDT", "side": "LONG", "qty": 0.5},
            {"event_type": "PROOF_OPEN", "symbol": "ETHUSDT", "side": "SHORT", "qty": 1.0},
            {"event_type": "PROOF_CLOSE", "symbol": "ETHUSDT", "side": "SHORT", "qty": 1.0}, # Closed
            {"event_type": "PROOF_OPEN", "symbol": "SOLUSDT", "side": "LONG", "qty": 10.0}, 
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
            temp_path = Path(f.name)
            
        try:
            positions = get_internal_positions_from_events(temp_path)
            
            # BTC should be +0.5
            self.assertIn("BTCUSDT", positions)
            self.assertAlmostEqual(positions["BTCUSDT"], 0.5)
            
            # ETH should be gone (0.0)
            self.assertNotIn("ETHUSDT", positions)
            
            # SOL should be +10.0
            self.assertIn("SOLUSDT", positions)
            self.assertAlmostEqual(positions["SOLUSDT"], 10.0)
            
        finally:
            temp_path.unlink()

    def test_lifecycle_events(self):
        """Test parsing ORDER_LIFECYCLE_DONE events."""
        events = [
            # Open BTC Long
            {"event_type": "ORDER_LIFECYCLE_DONE", "action": "OPEN", "symbol": "BTCUSDT", "side": "BUY", "filled_qty": 0.2},
            # Open ETH Short
            {"event_type": "ORDER_LIFECYCLE_DONE", "action": "OPEN", "symbol": "ETHUSDT", "side": "SELL", "filled_qty": 2.0},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
            temp_path = Path(f.name)
            
        try:
            positions = get_internal_positions_from_events(temp_path)
            
            self.assertAlmostEqual(positions["BTCUSDT"], 0.2)
            self.assertAlmostEqual(positions["ETHUSDT"], -2.0)
            
        finally:
            temp_path.unlink()
            
    def test_ignore_zero_positions(self):
        """Zero positions should be filtered out."""
        events = [
            {"event_type": "PROOF_OPEN", "symbol": "BTCUSDT", "qty": 0.0},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
            temp_path = Path(f.name)
            
        try:
            positions = get_internal_positions_from_events(temp_path)
            self.assertNotIn("BTCUSDT", positions)
        finally:
            temp_path.unlink()
            
    def test_missing_file_returns_empty(self):
        """Missing file should return empty dict, not crash."""
        fake_path = Path("/nonexistent/file.ndjson")
        positions = get_internal_positions_from_events(fake_path)
        self.assertEqual(positions, {})

if __name__ == "__main__":
    unittest.main()
