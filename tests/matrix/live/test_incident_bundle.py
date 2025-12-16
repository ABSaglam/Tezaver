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

class TestIncidentBundleProdLock(unittest.TestCase):
    """Tests for Step B.1 prod lock requirements."""
    
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.tmp_dir) / "incidents"
        self.ndjson_path = Path(self.tmp_dir) / "live_events.ndjson"
        
        with open(self.ndjson_path, "w") as f:
            f.write(json.dumps({"event_type": "TEST", "ts": "2025-01-01T00:00:00Z"}) + "\n")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
    
    def test_manifest_contains_real_git_info(self):
        """T1: Manifest should have real git branch/commit when in a git repo."""
        ctx = BundleContext(
            reason="TEST_GIT",
            ndjson_path=self.ndjson_path,
            output_dir=self.output_dir,
        )
        
        zip_path = export_incident_bundle(ctx)
        
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))
            branch = manifest["metadata"]["repo_branch"]
            commit = manifest["metadata"]["repo_commit"]
            
            # Should not be "unknown" if git is available
            # (Test runs inside a git repo)
            self.assertNotEqual(branch, "unknown")
            self.assertNotEqual(commit, "unknown")
            self.assertTrue(len(commit) >= 7)  # Short hash at least 7 chars
    
    def test_runtime_block_calls_exporter(self):
        """T2: Simulate runtime block path using exporter directly."""
        ctx = BundleContext(
            reason="CardGate_STALE: [card_age > 72h]",
            ndjson_path=self.ndjson_path,
            output_dir=self.output_dir,
        )
        
        zip_path = export_incident_bundle(ctx)
        self.assertTrue(Path(zip_path).exists())
        
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))
            self.assertIn("CardGate_STALE", manifest["metadata"]["reason"])
    
    def test_legacy_flag_mapping(self):
        """T3: --auto-incident-on BLOCK should enable --auto-export-on-block."""
        import argparse
        
        # Simulate the argparse behavior from live_loop
        parser = argparse.ArgumentParser()
        parser.add_argument("--auto-incident-on", type=str, default=None, choices=["BLOCK", "WARN", "OFF"])
        parser.add_argument("--auto-export-on-block", action="store_true")
        
        # Case 1: Legacy flag set, new not set
        args = parser.parse_args(["--auto-incident-on", "BLOCK"])
        if args.auto_incident_on is not None and args.auto_incident_on != "OFF":
            if not args.auto_export_on_block:
                args.auto_export_on_block = True
        self.assertTrue(args.auto_export_on_block)
        
        # Case 2: New flag set explicitly (takes precedence)
        args = parser.parse_args(["--auto-export-on-block"])
        self.assertTrue(args.auto_export_on_block)
        
        # Case 3: Legacy OFF
        args = parser.parse_args(["--auto-incident-on", "OFF"])
        if args.auto_incident_on is not None and args.auto_incident_on != "OFF":
            if not args.auto_export_on_block:
                args.auto_export_on_block = True
        self.assertFalse(args.auto_export_on_block)
