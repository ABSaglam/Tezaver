# Test Matrix Health / Lock Summarization
"""Unit tests for summarize_locks_from_ndjson in matrix_operator_data."""

import unittest
import tempfile
import json
from pathlib import Path
from tezaver.ui.matrix_operator_data import summarize_locks_from_ndjson


class TestSummarizeLocks(unittest.TestCase):
    """Tests for lock state extraction from NDJSON."""
    
    def test_missing_ndjson_returns_unknown_states(self):
        """Missing NDJSON file should return UNKNOWN states."""
        fake_path = Path("/nonexistent/file.ndjson")
        result = summarize_locks_from_ndjson(fake_path)
        
        self.assertEqual(result["preflight"]["state"], "UNKNOWN")
        self.assertEqual(result["card_gate"]["state"], "UNKNOWN")
        self.assertEqual(result["risk"]["state"], "UNKNOWN")
        self.assertEqual(result["reconcile"]["state"], "UNKNOWN")
        self.assertIsNone(result["last_block_reason"])
    
    def test_empty_ndjson_returns_unknown_states(self):
        """Empty NDJSON file should return UNKNOWN states."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            f.write("")
            temp_path = Path(f.name)
        
        try:
            result = summarize_locks_from_ndjson(temp_path)
            self.assertEqual(result["preflight"]["state"], "UNKNOWN")
        finally:
            temp_path.unlink()
    
    def test_preflight_eval_parsed_correctly(self):
        """PREFLIGHT_EVAL event should set preflight state."""
        events = [
            {"event_type": "PREFLIGHT_EVAL", "decision": "PASS", "ts": "2024-01-01T00:00:00Z"},
            {"event_type": "PREFLIGHT_EVAL", "decision": "BLOCK", "failed_checks": ["margin_check"], "ts": "2024-01-01T01:00:00Z"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
            temp_path = Path(f.name)
        
        try:
            result = summarize_locks_from_ndjson(temp_path)
            # Last event wins
            self.assertEqual(result["preflight"]["state"], "BLOCK")
            self.assertIn("margin_check", result["preflight"]["reason"])
            self.assertIn("Preflight", result["last_block_reason"])
        finally:
            temp_path.unlink()
    
    def test_card_gate_eval_parsed_correctly(self):
        """CARD_GATE_EVAL event should set card_gate state."""
        events = [
            {"event_type": "CARD_GATE_EVAL", "allow": True, "ts": "2024-01-01T00:00:00Z"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
            temp_path = Path(f.name)
        
        try:
            result = summarize_locks_from_ndjson(temp_path)
            self.assertEqual(result["card_gate"]["state"], "PASS")
        finally:
            temp_path.unlink()
    
    def test_risk_limit_block_parsed_correctly(self):
        """RISK_LIMIT_BLOCK event should set risk state to BLOCK."""
        events = [
            {"event_type": "RISK_LIMIT_BLOCK", "allow": False, "reason": "max notional exceeded", "ts": "2024-01-01T00:00:00Z"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
            temp_path = Path(f.name)
        
        try:
            result = summarize_locks_from_ndjson(temp_path)
            self.assertEqual(result["risk"]["state"], "BLOCK")
            self.assertIn("max notional", result["risk"]["reason"])
            self.assertIn("Risk", result["last_block_reason"])
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    unittest.main()
