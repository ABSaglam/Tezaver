"""
Tests for Matrix Operator Data Helpers
"""

import unittest
import tempfile
import shutil
import json
import zipfile
from pathlib import Path

from tezaver.ui.matrix_operator_data import (
    load_ndjson_tail,
    summarize_health,
    list_incident_bundles,
    read_bundle_manifest,
    filter_events,
    BundleInfo,
)


class TestLoadNdjsonTail(unittest.TestCase):
    
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.ndjson_path = Path(self.tmp_dir) / "events.ndjson"
    
    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
    
    def test_handles_missing_file(self):
        """Should return empty list if file doesn't exist."""
        result = load_ndjson_tail(Path("/nonexistent/path.ndjson"))
        self.assertEqual(result, [])
    
    def test_reads_tail_correctly(self):
        """Should read last N lines."""
        with open(self.ndjson_path, "w") as f:
            for i in range(10):
                f.write(json.dumps({"idx": i}) + "\n")
        
        result = load_ndjson_tail(self.ndjson_path, max_lines=3)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["idx"], 7)
        self.assertEqual(result[2]["idx"], 9)


class TestSummarizeHealth(unittest.TestCase):
    
    def test_picks_latest_per_event_type(self):
        """Should return the latest event of each type."""
        events = [
            {"event_type": "PREFLIGHT_EVAL", "decision": "PASS", "ts": "T1"},
            {"event_type": "PREFLIGHT_EVAL", "decision": "BLOCK", "ts": "T2"},
            {"event_type": "RISK_LIMIT_CHECK", "decision": "PASS", "allow": True, "ts": "T3"},
            {"event_type": "INCIDENT_BUNDLE_EXPORTED", "path": "/a.zip", "reason": "TEST", "ts": "T4"},
        ]
        
        summary = summarize_health(events)
        
        # Latest PREFLIGHT should be BLOCK
        self.assertEqual(summary["preflight"]["decision"], "BLOCK")
        self.assertEqual(summary["preflight"]["ts"], "T2")
        
        # Risk limit check
        self.assertEqual(summary["risk_limit"]["allow"], True)
        
        # Incident bundle
        self.assertEqual(summary["incident_bundle"]["path"], "/a.zip")
    
    def test_empty_events_returns_all_none(self):
        """Should return None for all keys if no events."""
        summary = summarize_health([])
        self.assertIsNone(summary["preflight"])
        self.assertIsNone(summary["incident_bundle"])


class TestListIncidentBundles(unittest.TestCase):
    
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.incident_dir = Path(self.tmp_dir) / "incidents"
        self.incident_dir.mkdir()
    
    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
    
    def test_reads_manifest_from_zip(self):
        """Should read manifest.json from inside zip."""
        # Create a test bundle
        zip_path = self.incident_dir / "incident_bundle_20250101T000000Z.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            manifest = {
                "metadata": {
                    "created_ts_utc": "2025-01-01T00:00:00Z",
                    "reason": "TEST_REASON",
                    "repo_commit": "abc123",
                },
                "files": [{"name": "a.txt"}, {"name": "b.txt"}]
            }
            zf.writestr("manifest.json", json.dumps(manifest))
        
        bundles = list_incident_bundles(self.incident_dir)
        
        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].reason, "TEST_REASON")
        self.assertEqual(bundles[0].repo_commit, "abc123")
        self.assertEqual(bundles[0].files_count, 2)
    
    def test_missing_dir_returns_empty(self):
        """Should return empty list if dir doesn't exist."""
        result = list_incident_bundles(Path("/nonexistent"))
        self.assertEqual(result, [])
    
    def test_corrupt_zip_handled(self):
        """Should return bundle with error field for corrupt zip."""
        zip_path = self.incident_dir / "incident_bundle_bad.zip"
        with open(zip_path, "w") as f:
            f.write("not a zip file")
        
        bundles = list_incident_bundles(self.incident_dir)
        self.assertEqual(len(bundles), 1)
        self.assertIsNotNone(bundles[0].error)
        self.assertIn("corrupt", bundles[0].error)


class TestFilterEvents(unittest.TestCase):
    
    def test_filters_by_event_type(self):
        """Should filter by event type list."""
        events = [
            {"event_type": "A"},
            {"event_type": "B"},
            {"event_type": "A"},
        ]
        result = filter_events(events, event_types=["A"])
        self.assertEqual(len(result), 2)
    
    def test_filters_by_symbol(self):
        """Should filter by symbol."""
        events = [
            {"event_type": "X", "symbol": "BTC"},
            {"event_type": "X", "symbol": "ETH"},
        ]
        result = filter_events(events, symbol="BTC")
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
