"""
Tests for Incident Bundle Export
"""

import unittest
import shutil
import tempfile
import sys
import subprocess
import json
import zipfile
from pathlib import Path
from tezaver.matrix.live.incident_bundle import export_incident_bundle, BundleContext

class TestIncidentBundle(unittest.TestCase):
    
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.tmp_dir) / "incidents"
        self.ndjson_path = Path(self.tmp_dir) / "live_events.ndjson"
        self.log_path = Path(self.tmp_dir) / "live.log"
        
        # Create dummy log/events
        with open(self.ndjson_path, "w") as f:
            f.write(json.dumps({"event_type": "TEST_EVENT", "ts": "2025-01-01T00:00:00Z"}) + "\n")
        
        with open(self.log_path, "w") as f:
            f.write("Log line 1\nLog line 2\n")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_export_creates_zip_and_manifest(self):
        ctx = BundleContext(
            reason="TEST_BLOCK",
            ndjson_path=self.ndjson_path,
            log_file_path=self.log_path,
            config={"secret": "abc", "safe": "123"},
            output_dir=self.output_dir,
            last_n_events=10,
            last_n_log_lines=10
        )
        
        zip_path = export_incident_bundle(ctx)
        self.assertTrue(Path(zip_path).exists())
        self.assertTrue(zip_path.endswith(".zip"))
        
        # Verify content
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            self.assertIn("manifest.json", names)
            self.assertIn("live_events.ndjson", names)
            self.assertIn("recent_logs.txt", names)
            self.assertIn("config_snapshot.json", names)
            
            # Check manifest
            manifest = json.loads(zf.read("manifest.json"))
            self.assertEqual(manifest["metadata"]["reason"], "TEST_BLOCK")
            
            # Check redacted config
            cfg = json.loads(zf.read("config_snapshot.json"))
            self.assertEqual(cfg["safe"], "123")
            self.assertEqual(cfg["secret"], "[REDACTED]")

    def test_auto_export_triggered_on_block(self):
        """Integration test: --auto-export-on-block triggers export on Preflight BLOCK."""
        # Use FAKE_SYMBOL and CARD mode to trigger BLOCK
        cmd = [
            sys.executable, "-m", "tezaver.matrix.live.live_loop",
            "run",
            "--preflight",
            "--preflight-enforce", "BLOCK",
            "--symbols", "FAKE_SYMBOL_AUTO",
            "--open-rule-mode", "CARD_STRICT_WINDOW",
            "--runtime", "1",
            "--auto-export-on-block",
            "--incident-dir", str(self.output_dir)
        ]
        
        env = {"PYTHONPATH": "src"}
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        # Expect exit code 2
        self.assertEqual(result.returncode, 2)
        self.assertIn("⛔ BLOCK EXIT: PREFLIGHT_BLOCK", result.stdout)
        self.assertIn("incident_bundle=", result.stdout)
        
        # Verify zip created
        generated = list(self.output_dir.glob("incident_bundle_*.zip"))
        self.assertTrue(len(generated) >= 1)

if __name__ == "__main__":
    unittest.main()
